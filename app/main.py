from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from fastapi.responses import StreamingResponse


from app.core.config import settings
from app.rag.generator import RAGService

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION
)

# 前端发过来的请求体
class ChatRequest(BaseModel):
    # ... 代表必填字段
    question: str = Field(..., min_length=2, description="用户提问")
    user_id: Optional[str] = "guest"

# 接口返回给前端的结构
class ChatResponse(BaseModel):
        status: str
        query: str
        answer: str
        references: List[Dict[str, Any]]

# 编写核心 API 接口路由与启动入口
@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    result = await RAGService.ask(request.question)
    return {
        "status": "success",
        "query": result["query"],
        "answer": result["answer"],
        "references": result["references"]
    }

# 新增：流式打字机专用接口！
@app.post("/api/v1/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    流式打字机接口：
    直接把 RAG 生成器对接给客户端，实现毫秒级首字响应！
    """
    return StreamingResponse(
        RAGService.ask_stream(request.question),
        media_type="text/plain; charset=utf-8"
    )

if __name__ == '__main__':
    import uvicorn
    uvicorn.run("app.main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=True)