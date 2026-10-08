# import asyncio
# from openai import AsyncOpenAI, base_url
# from app.core.config import settings
#
# # 1.连上我们之前配置好的大模型
# client = AsyncOpenAI(
#     api_key=settings.LLM_API_KEY,
#     base_url=settings.LLM_BASE_URL
# )
#
# async def real_llm_stream():
#     print("📡 正在向大模型发起流式提问...\n")
#
#     # 核心：加上stream=True
#     response = await client.chat.completions.create(
#         model=settings.LLM_MODEL,
#         messages=[
#             {"role": "user", "content": "请用 200 个字以内简要介绍一下顺德的美食。"}
#         ],
#         stream=True
#     )
#
#     async for chunk in response:
#         # 提取每一个增量小碎片里的字
#         content = chunk.choices[0].delta.content or ""
#         # 立刻像打字机一样打印在屏幕上
#         print(content, end="", flush=True)
#         await asyncio.sleep(0.03)
#
# # 启动异步
# asyncio.run(real_llm_stream())

import httpx

print("🚀 开始向 FastAPI 接口发起流式请求：\n")

# 加上 timeout=60.0 放宽等待时间！
with httpx.stream(
    "POST",
    "http://127.0.0.1:8000/api/v1/chat/stream",
    json={"question": "洗碗机E01怎么修？"},
    timeout=60.0  # 👈 给它 60 秒耐心！
) as response:
    for chunk in response.iter_text():
        print(chunk, end="", flush=True)

print("\n\n✅ 流式接收完成！")