import asyncio
from pathlib import Path
from typing import Dict, Any, List
from openai import AsyncOpenAI

from app.core.config import settings
from app.rag.chroma_engine import ChromaRAGEngine as RAGEngine

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


# 本地异步自测逻辑
if __name__ == "__main__":
    async def test():
        test_q = "师傅你好，我洗碗机报错 E01 该怎么修？"
        print(f"📡 正在向大模型发起异步提问: 【{test_q}】...\n")

        result = await RAGService.ask(test_q)

        print("=" * 50)
        print("🤖 AI 专家回复：")
        print(result["answer"])
        print("\n📚 参考手册溯源：", result["references"])
        print("=" * 50)


    # 启动 Python 异步事件循环
    asyncio.run(test())