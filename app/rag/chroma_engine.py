import json
import re
from pathlib import Path
from typing import List, Dict, Any
import chromadb
import numpy as np
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class ChineseFeatureEmbedding(EmbeddingFunction):
    """为 ChromaDB 量身定制的中文特征向量转换器（固定特征维度版）"""

    def __init__(self, reference_docs: List[str] = None):
        # 1. 建立固定的全局坐标轴词典
        self.vocab = {}
        if reference_docs:
            all_tokens = set()
            for doc in reference_docs:
                all_tokens.update(self._tokenize(doc))
            # 给每一个词固定的坐标轴编号
            self.vocab = {word: idx for idx, word in enumerate(sorted(all_tokens))}

    def _tokenize(self, text: str) -> List[str]:
        text = text.lower()
        tokens = []
        # 提取专有故障码（加双倍权重）
        codes = re.findall(r'[a-z0-9]+', text)
        for code in codes:
            tokens.extend([code, code])
        # 提取中文 1 字和 2 字
        chinese_chars = "".join(re.findall(r'[\u4e00-\u9fa5]', text))
        tokens.extend(list(chinese_chars))
        tokens.extend([chinese_chars[i:i + 2] for i in range(len(chinese_chars) - 1)])
        return tokens

    def __call__(self, input: Documents) -> Embeddings:
        """无论输入多少句话，永远投射到固定的 self.vocab 坐标空间中"""
        embeddings = []
        dim = max(len(self.vocab), 1)

        for text in input:
            tokens = self._tokenize(text)
            vec = [0.0] * dim
            for t in tokens:
                if t in self.vocab:
                    vec[self.vocab[t]] += 1.0

            # 模长归一化
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = (np.array(vec) / norm).tolist()
            embeddings.append(vec)
        return embeddings

class ChromaRAGEngine:
    def __init__(self, data_path: Path):
        self.data_path = data_path
        self.db_dir = BASE_DIR / "data" / "chroma_db"
        self.client = chromadb.PersistentClient(path=str(self.db_dir))

        # 1. 预先读取所有知识文本，用来锁定向量坐标轴
        with open(self.data_path, "r", encoding="utf-8") as f:
            docs = json.load(f)
        all_texts = [f"{d['title']} {d['category']} {d['content']}" for d in docs]

        # 2. 传入全量文本，锁定固定的中文特征空间！
        self.embed_fn = ChineseFeatureEmbedding(reference_docs=all_texts)

        # 3. 创建集合（命名为 aftersales_manual_v4）
        self.collection = self.client.get_or_create_collection(
            name="aftersales_manual_v4",
            embedding_function=self.embed_fn,
            metadata={"hnsw:space": "cosine"}
        )

        if self.collection.count() == 0:
            self._init_knowledge()

    def _init_knowledge(self):
        """读取 JSON 知识库，并持久化写入 ChromaDB 向量集合中"""
        print("📦 正在向 ChromaDB 写入初始维修手册数据...")
        with open(self.data_path, "r", encoding="utf-8") as f:
            docs = json.load(f)

        ids = [f"doc_{d['id']}" for d in docs]
        # 构建更富含语义的文本
        documents = [f"{d['title']} {d['category']} {d['content']}" for d in docs]
        metadatas = [{"id": d["id"], "title": d["title"], "category": d["category"]} for d in docs]

        # 一键入库！ChromaDB 会自动完成分词、特征提取与高维向量索引！
        self.collection.add(
            ids = ids,
            documents = documents,
            metadatas = metadatas
        )
        print(f"✅ 成功将 {len(docs)} 篇手册永久持久化至 ChromaDB！")

    def search(self,query: str, top_k: int = 2 ) -> List[Dict[str, Any]]:
        """
            核心检索：利用 ChromaDB 的 HNSW 空间索引进行极速相似度查询
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k
        )

        hits = []
        if not results["ids"] or not results["ids"][0]:
            return hits

        for i in range(len(results["ids"][0])):
            meta = results["metadatas"][0][i]
            doc_content = results["documents"][0][i]
            # ChromaDB 默认返回的是距离 distance（距离越小越相似），我们把它转换为相似度得分
            # distance = results["distances"][0][i] if "distances" in results and results["distances"] else 1.0
            # similarity_score = round(max(0.0, 1.0 - distance), 4)
            # 余弦距离在 0 到 2 之间，0 表示完全一致。相似度 = 1.0 - 距离
            distance = results["distances"][0][i] if "distances" in results else 1.0
            similarity_score = round(max(0.0, 1.0 - distance), 4)
            hits.append({
                "id":meta["id"],
                "title": meta["title"],
                "category": meta["category"],
                "content": doc_content,
                "similarity_score": similarity_score
            })

        return hits

if __name__ == '__main__':
    knowledge_file = BASE_DIR / "data" / "knowledge.json"
    engine = ChromaRAGEngine(data_path=knowledge_file)

    print("=" * 45)
    print(f"📊 ChromaDB 当前集合文档总数: {engine.collection.count()}")
    print("=" * 45)

    test_queries = [
        "为什么我洗完后盘子摸起来还是油腻腻的？",
        "机器报错 E01 怎么处理？"
    ]

    for q in test_queries:
        print(f"\n🔍 用户提问: 【{q}】")
        hits = engine.search(q, top_k=1)
        if hits:
            best = hits[0]
            print(f"🎯 命中手册: 《{best['title']}》 (相似度得分: {best['similarity_score']})")
            print(f"📄 检索内容: {best['content'][:60]}...")
        else:
            print("❌ 未检索到相关资料")