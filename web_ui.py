import uuid
import httpx
import streamlit as st
from app.db.database import get_recent_orders, get_session_chat_logs

# 1. 页面基本配置
st.set_page_config(
    page_title="智能家电售后 RAG 助手",
    page_icon="🔧",
    layout="wide"  # 👈 改为 wide 宽屏布局，左右对比更舒服！
)

# 2. 侧边栏设计（控制面板 + 实时工单看板）
with st.sidebar:
    st.header("⚙️ 售后系统控制台")
    st.caption("基于 FastAPI + ChromaDB + SQLite + Agent 构建")

    # 会话 ID
    if "session_id" not in st.session_state:
        st.session_state.session_id = f"user_{uuid.uuid4().hex[:6]}"

    st.info(f"🆔 当前会话: `{st.session_state.session_id}`")

    # 开启新会话按钮
    if st.button("🧹 开启新对话", use_container_width=True):
        st.session_state.messages = [
            {"role": "assistant", "content": "您好！我是顺德家电智能售后专家，请问您的机器遇到了什么故障？"}
        ]
        st.session_state.session_id = f"user_{uuid.uuid4().hex[:6]}"
        st.rerun()

    st.divider()

    # ---------------- 🌟 新增：实时派工看板 ----------------
    col_title, col_btn = st.columns([3, 1])
    with col_title:
        st.subheader("📋 实时派工看板")
    with col_btn:
        if st.button("🔄", help="刷新工单列表"):
            st.rerun()

    orders = get_recent_orders(limit=8)
    if not orders:
        st.caption("暂无待派工单记录")
    else:
        st.caption(f"📊 数据库已有 **{len(orders)}** 条最新工单记录：")
        for ord in orders:
            # 状态卡片展示
            with st.expander(f"📦 {ord['order_no']}（{ord['appliance']}）", expanded=False):
                st.markdown(f"**故障描述**：`{ord['fault_desc']}`")
                st.markdown(f"**服务地址**：{ord['address']}")
                st.markdown(f"**联系电话**：{ord['phone']}")
                st.markdown(f"**派工状态**：🟡 `{ord['status']}`")
                st.caption(f"🕒 下单时间：{ord['created_at']}")

                # 🌟 【企业级问诊溯源】：点击展开此单产生时的全部聊天记录
                session_id = ord.get("session_id", "default")
                chat_logs = get_session_chat_logs(session_id)
                with st.expander("💬 报修排查问诊记录", expanded=False):
                    if not chat_logs:
                        st.caption("暂无问诊记录（离线或历史导入工单）")
                    else:
                        for log in chat_logs:
                            icon = "👤" if log["role"] == "user" else "🤖"
                            role_name = "用户" if log["role"] == "user" else "AI专家"
                            st.markdown(f"**{icon} {role_name}** (`{log['created_at'][11:]}`):")
                            st.caption(log["content"][:120] + ("..." if len(log["content"]) > 120 else ""))
# 3. 页面大标题与介绍
st.title("🔧 智能家电售后专家")
st.caption("🚀 顺德智能制造知识库实时驱动 | 毫秒级语义溯源 | 自动派工 Agent")

# 4. 初始化历史消息抽屉
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "您好！我是顺德家电智能售后专家，请问您的机器遇到了什么故障？"}
    ]

# 5. 渲染历史聊天气泡
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 6. 从后端接收流式数据的生成器
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
user_input = st.chat_input("请详细描述您的家电故障或报修需求...")

if user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        stream_data = fetch_stream_from_backend(user_input, st.session_state.session_id)
        full_reply = st.write_stream(stream_data)

    st.session_state.messages.append({"role": "assistant", "content": full_reply})

    # 如果回答中检测到派单成功标记，自动刷新一下页面，让左边看板瞬间显示新工单！
    if "工单编号" in full_reply or "SHD-" in full_reply:
        st.rerun()