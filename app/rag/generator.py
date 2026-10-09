import asyncio
from idlelib import history
from pathlib import Path
from typing import Dict, Any, List
from openai import AsyncOpenAI

from app.core.config import settings
from app.rag.chroma_engine import ChromaRAGEngine as RAGEngine
from app.rag.memory import session_memory

# 1. 初始化标准异步大模型客户端
client = AsyncOpenAI(
    api_key=settings.LLM_API_KEY,
    base_url=settings.LLM_BASE_URL
)

# 2. 知识库定位与检索引擎初始化
BASE_DIR = Path(__file__).resolve().parent.parent.parent
data_file = BASE_DIR / "data" / "knowledge.json"
engine = RAGEngine(data_path=data_file)


class RAGService:
    """RAG 智能问答业务编排服务"""

    @staticmethod
    def _build_prompt(query: str, references: List[Dict[str, Any]]) -> str:
        """组装带有知识库参考资料的安全提示词"""
        if not references:
            ref_text = "（知识库中暂未检索到高度相关的官方手册条款）"
        else:
            ref_snippets = []
            for idx, doc in enumerate(references, 1):
                ref_snippets.append(
                    f"【手册 {idx}：{doc['title']}】\n"
                    f"分类：{doc['category']}\n"
                    f"条文内容：{doc['content']}"
                )
            ref_text = "\n\n".join(ref_snippets)

        prompt = f"""你是一名专业的智能家电售后技术支持专家。请严格基于以下【官方维修手册】的内容回答用户的问题。

【官方维修手册参考资料】：
{ref_text}

【用户问题】：
{query}

【回答要求】：
1. 严格以提供的手册内容为依据，用亲切、清晰、条理分明的步骤解答。
2. 若手册中有安全警告（如断电、切勿自行拆解等），必须在回答开头予以醒目标注！
3. 若手册中未提及相关故障，请明确告知用户该问题不在当前售后手册范围，建议联系官方人工客服，严禁胡编乱造！"""
        return prompt

    @classmethod
    async def ask(cls, query: str) -> Dict[str, Any]:
        """
        核心异步问答方法：
        1. 语义检索知识库
        2. 动态组装 Prompt
        3. 异步调用大模型
        """
        # 第一步：检索前 2 条最相关的知识
        hits = engine.search(query, top_k=2)

        # 记录命中的手册标题与 ID（用于后续前端溯源展示）
        reference_info = [
            {"id": h["id"], "title": h["title"], "score": h["similarity_score"]}
            for h in hits
        ]

        # 第二步：组装包含知识的 Prompt
        full_prompt = cls._build_prompt(query, hits)

        # 第三步：异步调用大模型（温度设为 0.1 保证严谨）
        response = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": "你是由顺德智能制造基地训练的企业级售后服务专家。"},
                {"role": "user", "content": full_prompt}
            ],
            temperature=0.1
        )

        answer_text = response.choices[0].message.content

        return {
            "query": query,
            "answer": answer_text,
            "references": reference_info
        }

    # @classmethod
    # async def ask_stream(cls,query:str):
    #     """
    #        核心异步流式问答水龙头：
    #        1. 检索知识库
    #        2. 开启大模型流式传输
    #        3. 用 yield 逐字实时吐出回答文本
    #     """
    #     # 第一步：检索相关知识手册
    #     hits = engine.search(query, top_k=2)
    #     full_prompt = cls._build_prompt(query,hits)
    #
    #     # 第二步：调用大模型，打开流式阀门 stream=True！
    #     response = await client.chat.completions.create(
    #         model=settings.LLM_MODEL,
    #         messages=[
    #             {"role": "system", "content": "你是由顺德智能制造基地训练的企业级售后服务专家。"},
    #             {"role": "user", "content": full_prompt}
    #         ],
    #         stream=True,
    #         temperature=0.1
    #     )
    #
    #     # 第三步：只要网线收到一个字，立刻用 yield 吐给外面！
    #     async for chunk in response:
    #         content = chunk.choices[0].delta.content or ""
    #         if content:
    #             yield content
    #
    #     # 第四步：打字结束后，顺手在末尾吐出参考手册溯源！
    #     if hits:
    #         yield "\n\n---\n📚 **参考官方手册溯源：**\n"
    #         for h in hits:
    #             yield f"- 《{h['title']}》 (相似度得分: {h['similarity_score']})\n"

    @classmethod
    async def ask_stream(cls, query: str, session_id: str = "default"):
        """
        升级版流式问答水龙头（支持多轮记忆于指代小姐）
        :param query: 当前提问
        :param session_id: 用户id
        :return:
        """

        # 1. 取出当前用户的历史记忆
        history = session_memory.get_history(session_id)

        # 2.如果有历史，自动执行指代消解重写
        search_query = query
        if history:
            search_query = await cls.rewrite_query(history, query)
            # 贴心提示：如果发生了改写，悄悄在最开始提示一下改写后的问题
            if search_query != query:
                yield f"💡 *[智能理解：已结合上下文将提问理解为「{search_query}」]*\n\n"

        # 3.拿着最精准的搜索词去查 ChromaDB
        hits = engine.search(search_query, top_k=2)
        full_prompt = cls._build_prompt(search_query, hits)

        # 4. 调用大模型开启流式传输
        # 构造发给大模型的消息：包含历史对话 + 当前增强提问
        messages = [{"role": "system", "content": "你是由顺德智能制造基地训练的企业级售后服务专家。"}]
        # 塞入历史消息（最近 3 轮）
        for msg in history:
            messages.append(msg)
        # 塞入当前带着手册知识的完整 Prompt
        messages.append({"role": "user", "content": full_prompt})

        response = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=messages,
            stream=True,
            temperature=0.1
        )

        # 5.一遍yield吐字i，一边在后台攒完整回答，用于记入会话历史
        full_assistant_reply = ""
        async for chunk in response:
            content = chunk.choices[0].delta.content or ""
            if content:
                full_assistant_reply += content
                yield content

        # 6.吐出溯源手册
        if hits:
            yield "\n\n---\n📚 **参考官方手册溯源：**\n"
            for h in hits:
                yield f"- 《{h['title']}》 (相似度得分: {h['similarity_score']})\n"

        # 7.核心闭环： 问答彻底结束后，把本轮对话存入会话历史中
        session_memory.add_turn(session_id,query,full_assistant_reply)


    @classmethod
    async def rewrite_query(cls, history: list, latest_query: str) -> str:
        """根据上下文历史，自动消解代词，将问题重写为独立的搜索语境"""
        if not history:
            return latest_query

        context = ""
        for msg in history:
            context += f"{msg['role']}: {msg['content']}\n"

        system_prompt = (
            "你是一个智能搜索提问改写专家。\n"
            "请根据对话上下文，将用户最新提问改写为一个【语义完整、独立、不带指代代词（如它、这个、那）】的问题。\n"
            "如果用户提问本身已经很完整或与上文无关，请直接输出原问题，不要做任何解释！"
        )

        user_prompt = f"【对话上下文】：\n{context}\n\n【用户最新提问】：\n{latest_query}\n\n请输出改写后的独立问题："

        response = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature = 0.0
        )

        return response.choices[0].message.content.strip()

# 本地异步自测逻辑
if __name__ == "__main__":
    async def test():
        test_q = "师傅你好，我洗碗机报错 E01 该怎么修？"
        print(f"📡 正在向大模型发起异步提问: 【{test_q}】...\n")

        # 用 async for 接住我们新写的流式水龙头！
        async for word in RAGService.ask_stream(test_q):
            print(word, end="", flush=True)

    # 启动 Python 异步事件循环
    asyncio.run(test())