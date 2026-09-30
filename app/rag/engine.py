import json
from pathlib import Path
from typing import List, Dict, Any
import numpy as np
import re

class RAGEngine:
    """ RAG 知识检索核心引擎 """

    def __init__(self, data_path: Path):
        self.data_path = data_path
        self.documents: List[Dict[str, Any]] = []
        self.vocabulary: Dict[str, int] = {}
        self.doc_vectors: np.ndarray = np.array([])

        # 初始化是自动加载知识库并建立向量索引
        self._load_and_index()

    def _load_and_index(self):
        """1. 读取知识库 JSON 并建立词表与文档向量"""
        if not self.data_path.exists():
            raise FileNotFoundError(f"知识库文件不存在: {self.data_path}")

        with open(self.data_path, "r", encoding="utf-8") as f:
            self.documents = json.load(f)

        # 提取所有文档中的特征词，构建词汇表（字典）
        all_words = set()
        for doc in self.documents:
            text = f"{doc['title']} {doc['category']} {doc['content']}"
            # 提取字符特征
            all_words.update(self._tokenize(text))

        self.vocabulary = {word: idx for idx, word in enumerate(sorted(all_words))}

        # 把每篇知识文档转化为高维向量矩阵
        vectors = [self._vectorize(f"{d['title']} {d['category']} {d['content']}") for d in self.documents]
        self.doc_vectors = np.array(vectors)

    # def _tokenize(self, text: str) -> List[str]:
    #     # """分词：提取 2 字重叠语法切片（N-gram），保证无需复杂第三方分词库也能精准捕捉中文语义"""
    #     # clean_text = "".join(char for char in text.lower() if char.isalnum())
    #     # return [clean_text[i:i+2] for i in range(len(clean_text) - 1)]
    #
    #     """
    #     分词升级版：同时提取 1 字（单字核心）与 2 字（词组搭配）
    #     让 '油'、'洗' 等单字也能建立关联，大幅提升口语化检索召回率！
    #     """
    #     clean_text = "".join(char for char in text.lower() if char.isalnum())
    #     if not clean_text:
    #         return []
    #
    #     # 提取 1 字特征
    #     unigrams = list(clean_text)
    #     # 提取 2 字重叠特征
    #     bigrams = [clean_text[i:i + 2] for i in range(len(clean_text) - 1)]
    #
    #     return unigrams + bigrams

    def _tokenize(self, text: str) -> List[str]:
        """
        工业级分词：
        1. 优先提取完整的英文数字故障码（如 e01, e04, 10a）
        2. 中文提取单字与双字
        """
        text = text.lower()
        tokens = []

        # 1. 提取完整的英文数字组合（故障代码核心）
        codes = re.findall(r'[a-z0-9]+', text)
        for code in codes:
            # 对于故障码（如 e01），赋予更高权重（重复添加两次）
            tokens.append(code)
            tokens.append(code)

        # 2. 清洗中文并提取 1 字和 2 字
        chinese_chars = re.findall(r'[\u4e00-\u9fa5]', text)
        clean_chinese = "".join(chinese_chars)

        # 中文单字
        tokens.extend(list(clean_chinese))
        # 中文双字切片
        tokens.extend([clean_chinese[i:i + 2] for i in range(len(clean_chinese) - 1)])

        return tokens

    def _vectorize(self, text:str) -> np.ndarray:
        """把一段文本转化成数学向量"""
        tokens = self._tokenize(text)
        vec = np.zeros(len(self.vocabulary), dtype=float)
        for token in tokens:
            if token in self.vocabulary:
                vec[self.vocabulary[token]] += 1.0

        # 进行向量模长归一化（使计算余弦相似度时直接用点积）
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec

    def search(self, query: str, top_k: int = 2) -> List[Dict[str, Any]]:
        """
             核心检索方法：
             计算用户提问与知识库每一篇文档的余弦相似度，返回前 top_k 个最匹配的切片
        """
        query_vec = self._vectorize(query)
        if np.linalg.norm(query_vec) == 0:
            return []

        # 使用 NumPy 矩阵乘法极速计算与所有文档的余弦相似度得分
        scores = np.dot(self.doc_vectors, query_vec)

        # 按得分从高到低排序，提取前 top_k 的索引
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            score = float(scores[idx])
            # 过滤掉相似度几乎为 0 的无关结果
            if score > 0.05:
                doc = self.documents[idx].copy()
                doc["similarity_score"] = round(score, 4)
                results.append(doc)

        return results


# 本地自测逻辑
if __name__ == '__main__':
    # 定位到 data/knowledge.json 路径
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    data_file = BASE_DIR / "data" / "knowledge.json"

    engine = RAGEngine(data_path=data_file)
    print("=" * 45)
    print(f"✅ 知识库加载完毕，共收录 {len(engine.documents)} 条售后手册！")
    print(f"📐 向量空间维度: {len(engine.vocabulary)} 维")
    print("=" * 45)

    # 模拟真实用户的 2 种提问
    test_queries = [
        "为什么我洗完后盘子摸起来还是油腻腻的？",
        "机器报错 E01 怎么处理？"
        # "我的iphone无法开机怎么办？"
    ]

    for q in test_queries:
        print(f"\n🔍 用户提问: 【{q}】")
        hits = engine.search(q, top_k=1)
        if hits:
            best_hit = hits[0]
            print(f"🎯 命中手册: 《{best_hit['title']}》 (相似度得分: {best_hit['similarity_score']})")
            print(f"📄 检索内容: {best_hit['content'][:60]}...")
        else:
            print("❌ 未检索到相关资料")