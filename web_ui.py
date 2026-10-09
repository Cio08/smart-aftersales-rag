import uuid
import httpx
import streamlit as st

# 1. 页面基本配置（设置浏览器标签页标题与图标）
st.set_page_config(
    page_title="智能家电售后 RAG 助手",
    page_icon="🔧",
    layout="centered"
)

# 2. 侧边栏设计（控制面板）
with st.sidebar:
    st.header("⚙️ 售后系统控制台")
    st.caption("基于 FastAPI + ChromaDB + DeepSeek/Gemini 构建")

    # 为当前访客生成或保持一个固定的会话 ID
    if "session_id" not in st.session_state:
        st.session_state.session_id = f"user_{uuid.uuid4().hex[:6]}"

        st.info(f"🆔 当前会话: `{st.session_state.session_id}`")

    # 开启新会话按钮：清空抽屉，重置对话
    if st.button("🧹 开启新对话", use_container_width=True):
        st.session_state.messages = [
            {"role": "assistant", "content": "您好！我是顺德家电智能售后专家，请问您的机器遇到了什么故障？"}
        ]
        st.session_state.session_id = f"user_{uuid.uuid4().hex[:6]}"
        st.rerun()

# 3. 页面大标题与介绍
st.title("🔧 智能家电售后专家")
st.caption("🚀 顺德智能制造知识库实时驱动 | 毫秒级语义溯源 | 防幻觉安全守护")

# 4. 初始化历史消息抽屉
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "您好！我是顺德家电智能售后专家，请问您的机器遇到了什么故障？"}
    ]

# 5. 渲染抽屉里的所有历史聊天气泡
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 6. 从 FastAPI 后端接收流式打字机数据的生成器
def fetch_stream_from_backend(question: str, session_id: str):
    backend_url = "http://127.0.0.1:8000/api/v1/chat/stream"
    payload = {
        "question": question,
        "session_id": session_id
    }
    with httpx.stream("POST", backend_url, json=payload, timeout=60.0) as response:
        for chunk in response.iter_text():
            yield chunk

# 7. 接收用户输入并触发问答
user_input = st.chat_input("请详细描述您的家电故障（如报错代码、异常现象）...")

if user_input:
    # 立即展示用户的问题气泡
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    # 展示机器人气泡，并接入流式打字机！
    with st.chat_message("assistant"):
        stream_data = fetch_stream_from_backend(user_input, st.session_state.session_id)
        # st.write_stream 会自动渲染丝滑打字机动画，并在打字结束后返回完整文本！
        full_reply = st.write_stream(stream_data)

    # 问答结束，将完整回答存入抽屉
    st.session_state.messages.append({"role": "assistant", "content": full_reply})
