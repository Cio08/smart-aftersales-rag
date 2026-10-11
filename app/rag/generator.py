import asyncio
from pathlib import Path
from typing import Dict, Any, List
from openai import AsyncOpenAI
import json

from app.core.config import settings
from app.rag.chroma_engine import ChromaRAGEngine as RAGEngine
from app.rag.memory import session_memory
from app.tools.order_tool import TOOLS_DEFINITION, dispatch_tool


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
                    f"条文内容：{doc['content']}"
                )
            ref_text = "\n\n".join(ref_snippets)

        prompt =f"""你是一名专业的售后急诊技术专家。请务必【拒绝套话废话，一针见血，直奔用户核心问题】！

                    【官方维修手册参考资料】：
                    {ref_text}
                    
                    【用户问题】：
                    {query}
                    
                    【回答规则（严守逻辑，拒绝僵化）】：
                    1. 严禁寒暄废话（禁止“您好很高兴为您服务”等套话）。
                    2. 【排查优先原则】：若用户咨询故障，必须先给出 🚨 **【核心结论】**，再给出最多 3 步的 🛠️ **【处置步骤】**（动词加粗），最后说明 ⚠️ **【何时报修】**。
                    3. 【主动派单原则】：如果用户已明确尝试过排查无效、涉及硬件损坏必须换件，或用户明确要求“帮我预约师傅上门/报修”：
                       - 若用户已提供家电、电话、地址，请直接调用工具 `book_repair_technician` 录入工单！
                       - 若用户尚未提供电话或地址，请友好提醒用户留下联系电话和详细地址，以便安排师傅。
                    4. 【品类限定原则】：若用户询问非洗碗机品类（如洗衣机、冰箱等），严禁调用派单工具，必须明确告知当前仅支持洗碗机售后，并引导其拨打官方人工客服。
                """
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
        具备意图路由和阈值门禁的终极流式问答水龙头
        :param query: 当前提问
        :param session_id: 用户id
        :return:
        """
        try:
            # 第一步：前台分诊台识别意图
            intent = await cls.classify_intent(query)
            full_assistant_reply = ""

            # -------------------------------------------------------------
            # 🟢 分支 A：日常闲聊问候（CHITCHAT）➔ 不查知识库，极速礼貌回复！
            # -------------------------------------------------------------

            if intent == "CHITCHAT":
                response = await client.chat.completions.create(
                    model=settings.LLM_MODEL,
                    messages=[
                        {"role": "system",
                         "content": "你是顺德家电智能制造基地的官方售后专家，请以亲切、热情、专业的口吻回复客户的日常问候，并主动询问有什么家电故障可以协助排查。"},
                        {"role": "user", "content": query}
                    ],
                    stream=True,
                    temperature=0.7
                )
                async for chunk in response:
                    content = chunk.choices[0].delta.content or ""
                    if content:
                        full_assistant_reply += content
                        yield content

                # 存入记忆并直接结束！
                session_memory.add_turn(session_id, query, full_assistant_reply)
                return

            # -------------------------------------------------------------
            # 🔴 分支 B：真实故障报修（FAULT_DIAGNOSIS）➔ 走专业 RAG 流程
            # -------------------------------------------------------------

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

            # 【核心安全锁】：阈值过滤，低于 0.18 的弱相关手册视为“未收录”
            valid_hits = [h for h in hits if h["similarity_score"] >= 0.18]

            full_prompt = cls._build_prompt(search_query, valid_hits)

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
                tools=TOOLS_DEFINITION,     # 递上派单工具箱
                tool_choice="auto",
                stream=True,
                temperature=0.1
            )

            # 5. 一边接收数据流，一边判断：大模型是在打字，还是在发调用指令？
            tool_calls_accumulator = {}

            async for chunk in response:
                delta = chunk.choices[0].delta

                # 情况A： 大模型发来了工具调用的参数碎片
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        # 先看看该碎片的信息受否已收录，没收录的话，以该碎片的索引为键，创建字典记录
                        if idx not in tool_calls_accumulator:
                            tool_calls_accumulator[idx] = {
                                "id": tc.id or "",
                                "name": tc.function.name or "",
                                "arguments": tc.function.arguments or ""
                            }
                        # 由于是流式输出，所以工具调用的参数会有碎片形式传回，那么碎片的索引一致的均存入以索引为键，其余参数为值的键值对中
                        else:
                            if tc.id:tool_calls_accumulator[idx]["id"] += tc.id
                            if tc.function.name: tool_calls_accumulator[idx]["name"] += tc.function.name
                            if tc.function.arguments: tool_calls_accumulator[idx]["arguments"] += tc.function.arguments

                # 情况B： 大模型在正常打字回答
                elif delta.content:
                    # 那么就边吐字回答边记录回复碎片
                    full_assistant_reply += delta.content
                    yield delta.content

            # 如果大模型决定调用工具派单
            if tool_calls_accumulator:
                # 取出要调用的工具信息
                tc = tool_calls_accumulator[0]
                func_name = tc["name"]
                func_args = json.loads(tc["arguments"])

                # 网页提醒
                yield "🛠️ *[系统自动调度：正在核验信息并录入顺德售后派工系统...]*\n\n"

                # 本地手脚真正执行写入数据库
                tool_result = dispatch_tool(func_name, func_args)

                # 将工具调用指令与执行结果追加进消息历史
                messages.append({
                    "role": "assistant",
                    "tool_calls": [{
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": func_name, "arguments": tc["arguments"]}
                    }]
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": tool_result
                })

                # 二次流式调用大模型：让它根据工单回执输出最终的体贴回复
                final_stream = await client.chat.completions.create(
                    model=settings.LLM_MODEL,
                    messages=messages,
                    stream=True,
                    temperature=0.1
                )
                async for chunk in final_stream:
                    content = chunk.choices[0].delta.content or ""
                    if content:
                        full_assistant_reply += content
                        yield content

            # 6.吐出溯源手册
            if valid_hits:
                yield "\n\n---\n📚 **参考官方手册溯源：**\n"
                for h in valid_hits:
                    yield f"- 《{h['title']}》 (相似度得分: {h['similarity_score']})\n"

            # 7.核心闭环： 问答彻底结束后，把本轮对话存入会话历史中
            session_memory.add_turn(session_id,query,full_assistant_reply)

        except Exception as e:
            # 【防弹衣】：捕获一切网络异常，优雅提示，绝不断网！
            yield f"\n\n⚠️ *[服务提示：网络通信出现轻微波动，已为您保留当前进度。请重新提问或稍后重试。原因：{str(e)[:50]}]*"

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

    @classmethod
    async def classify_intent(cls, query: str) -> str:
        """意图分诊器：判断用户是日常闲聊还是真实故障报修"""
        system_prompt = (
            "你是一个智能客服前台分诊器。请分析用户的输入，将其严格归类为以下两类之一：\n"
            "- CHITCHAT：纯日常问候、打招呼、感谢、无实际业务含义的闲聊（例如：你好、在吗、谢谢、天气真好）\n"
            "- FAULT_DIAGNOSIS：针对家电的故障咨询、使用疑问、报错代码、异常排查\n\n"
            "注意：你只能输出单词 CHITCHAT 或 FAULT_DIAGNOSIS，严禁输出任何多余的标点或汉字！"
        )
        response = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            temperature=0.0,
            max_tokens=10
        )

        return response.choices[0].message.content.strip()

# 本地异步自测逻辑
if __name__ == "__main__":
    async def test():
        test_q = "师傅你好，我家洗碗机漏水报错E04，我已经断电关水阀了，帮我叫师傅上门修一下吧，我电话是19203551306，地址在勒流公舍二楼"
        print(f"📡 正在向大模型发起异步提问: 【{test_q}】...\n")

        # 用 async for 接住我们新写的流式水龙头！
        async for word in RAGService.ask_stream(test_q):
            print(word, end="", flush=True)

    # 启动 Python 异步事件循环
    asyncio.run(test())