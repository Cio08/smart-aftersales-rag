# 智能家电售后 RAG 知识库问答系统 (Smart Aftersales RAG)

基于 **FastAPI + 高维语义向量检索 + 大模型异步调度** 构建的企业级智能售后问答系统。针对智能制造与家电售后场景中的长尾故障、模糊排查痛点，实现毫秒级精准检索、防幻觉生成与条文来源溯源。

---

## 🌟 核心特性

- **高并发异步架构**：基于 `FastAPI` + `httpx` / `AsyncOpenAI` 全链路非阻塞异步设计，极大提升单机吞吐量。
- **混合特征语义检索**：自主设计 1-gram / 2-gram 联合分词与正则特征保留算法，解决传统关键词在口语化提问（如“盘子油腻” vs “餐具油污”）和专有故障码（如 `E01`、`E04`）下的特征淹没与召回偏差。
- **严密防幻觉护栏**：采用 Prompt 动态注入与安全防护规则，严格限制大模型仅基于检索手册答题，遇到未知故障主动分流至人工售后。
- **可观测溯源机制**：响应结果附带 `references` 来源条文与相似度得分，支持前端高亮与快速归因排错。
- **严格工程规范**：全链路采用 Pydantic 数据强校验、虚拟环境隔离（`.venv`）与本地密钥安全隔离（`.env`）。

---

## 🛠️ 技术栈

- **后端框架**：FastAPI, Uvicorn, Pydantic v2
- **大语言模型**： DeepSeek（OpenAI 兼容协议）
- **科学计算与向量检索**：NumPy（余弦相似度计算）
- **环境与依赖**：Python 3.13, python-dotenv, Git

---

## 🚀 快速启动

### 1. 克隆项目并创建虚拟环境
```bash
git clone <your-repo-url>
cd smart-aftersales-rag
python -m venv .venv
.\.venv\Scripts\Activate.ps1  # Windows PowerShell
```
### 2. 安装依赖
```bash
pip install -r requirements.txt
```
### 3. 配置环境变量
复制 .env.example 为 .env，并填入你的大模型 API 密钥：
```bash
cp .env.example .env
```
### 4. 启动服务
```bash
python app/main.py
```
启动成功后，浏览器访问交互式接口文档：
👉 http://127.0.0.1:8000/docs