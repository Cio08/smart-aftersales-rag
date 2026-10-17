import uuid
import httpx
import streamlit as st
from app.db.database import (
    get_recent_orders,
    get_session_chat_logs,
    get_orders_statistics,
    update_order_status,
    get_distinct_sessions
)

# 1. 页面基本配置
st.set_page_config(
    page_title="顺德智造家电售后服务中枢",
    page_icon="🔧",
    layout="wide"  # 宽屏布局，大屏看板更震撼
)

# 2. 侧边栏：角色切换与系统信息
with st.sidebar:
    st.header("⚙️ 服务中枢控制台")

    # 🌟 核心：RBAC 角色切换单选框
    role = st.sidebar.radio(
        "🎭 切换当前身份",
        ["👤 客户报修与问诊", "🛠️ 网点主管（调度台）"],
        index=0
    )
    st.divider()

    # 会话 ID 初始化
    if "session_id" not in st.session_state:
        st.session_state.session_id = f"user_{uuid.uuid4().hex[:6]}"

    if role == "👤 客户报修与问诊":
        st.subheader("💬 会话管理")
        if st.button("➕ 开启新对话", use_container_width=True, type="primary"):
            new_id = f"user_{uuid.uuid4().hex[:6]}"
            st.session_state.session_id = new_id

            # 🌟 关键解药：强制同步下拉组件的 key 缓存，防止它倒退回旧会话！
            st.session_state["session_selector"] = new_id

            st.session_state.messages = [
                {"role": "assistant", "content": "您好！我是顺德家电智能售后专家，请问您的机器遇到了什么故障？"}
            ]
            st.rerun()

        st.caption(f"🆔 当前会话: `{st.session_state.session_id}`")

        # 🌟 核心升级：从 SQLite 调取历史活跃会话列表供用户自由切换
        recent_sessions = get_distinct_sessions(limit=10)

        session_options = []
        session_label_map = {}

        current_sid = st.session_state.session_id
        is_current_in_db = any(s["session_id"] == current_sid for s in recent_sessions)

        if not is_current_in_db:
            label = f"✨ 当前新对话 ({current_sid})"
            session_options.append(current_sid)
            session_label_map[current_sid] = label

        for s in recent_sessions:
            sid = s["session_id"]
            time_str = s["last_active"][5:16] if len(s["last_active"]) >= 16 else s["last_active"]
            label = f"💬 {sid} ({s['msg_count']}条 · {time_str})"
            session_options.append(sid)
            session_label_map[sid] = label

        if session_options:
            selected_idx = session_options.index(current_sid) if current_sid in session_options else 0
            chosen_sid = st.selectbox(
                "📜 历史对话切换",
                options=session_options,
                format_func=lambda x: session_label_map.get(x, x),
                index=selected_idx,
                key="session_selector"
            )
            # 用户在下拉菜单切换了会话
            if chosen_sid != current_sid:
                st.session_state.session_id = chosen_sid
                db_logs = get_session_chat_logs(chosen_sid)
                if db_logs:
                    st.session_state.messages = [
                        {"role": log["role"], "content": log["content"]} for log in db_logs
                    ]
                else:
                    st.session_state.messages = [
                        {"role": "assistant", "content": "您好！我是顺德家电智能售后专家，请问您的机器遇到了什么故障？"}
                    ]
                st.rerun()

    else:
        st.caption("🔑 已进入管理权限模式")
        st.caption("负责区域工单调度、进度流转与服务质检。")

# ========================================================
# 视图 A：【👤 客户报修与问诊门户】
# ========================================================
if role == "👤 客户报修与问诊":
    st.title("🔧 智能家电售后专家")
    st.caption("🚀 顺德智能制造知识库实时驱动 | 毫秒级语义溯源 | 自动化派工 Agent")

    # 初始化历史消息抽屉（优先从 SQLite 回填）
    if "messages" not in st.session_state:
        db_logs = get_session_chat_logs(st.session_state.session_id)
        if db_logs:
            st.session_state.messages = [
                {"role": log["role"], "content": log["content"]} for log in db_logs
            ]
        else:
            st.session_state.messages = [
                {"role": "assistant", "content": "您好！我是顺德家电智能售后专家，请问您的机器遇到了什么故障？"}
            ]

    # 渲染历史聊天气泡
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])


    # 从后端接收流式数据的生成器
    def fetch_stream_from_backend(question: str, session_id: str):
        backend_url = "http://127.0.0.1:8000/api/v1/chat/stream"
        payload = {"question": question, "session_id": session_id}
        with httpx.stream("POST", backend_url, json=payload, timeout=60.0) as response:
            for chunk in response.iter_text():
                yield chunk


    # 接收用户提问
    user_input = st.chat_input("请详细描述您的家电故障或报修需求...")
    if user_input:
        with st.chat_message("user"):
            st.markdown(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})

        with st.chat_message("assistant"):
            stream_data = fetch_stream_from_backend(user_input, st.session_state.session_id)
            full_reply = st.write_stream(stream_data)

        st.session_state.messages.append({"role": "assistant", "content": full_reply})


# ========================================================
# 视图 B：【🛠️ 网点主管（调度台）】
# ========================================================
else:
    st.title("🛠️ 顺德家电售后服务中枢 · 网点调度指挥台")
    st.caption("📊 实时派工监控 | 工单全生命周期流转 | 全链路问诊溯源")

    # 1. 顶部 KPI 数据大屏指标卡
    stats = get_orders_statistics()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="📦 累计报修总量", value=f"{stats['total']} 单")
    with col2:
        st.metric(label="🟡 待派工（待处理）", value=f"{stats['pending']} 单", delta=f"{stats['pending']} 待办",
                  delta_color="inverse")
    with col3:
        st.metric(label="🔵 维修中（在途）", value=f"{stats['processing']} 单")
    with col4:
        st.metric(label="🟢 已完工（闭环）", value=f"{stats['completed']} 单")

    st.divider()

    # 2. 工单调度台控制条（筛选与刷新）
    ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([2, 1, 1])
    with ctrl_col1:
        status_filter = st.selectbox("🎯 快速按工单状态筛选", ["全部状态", "待派工", "维修中", "已完工"])
    with ctrl_col3:
        st.write("")  # 占位对齐
        if st.button("🔄 刷新调度台", use_container_width=True):
            st.rerun()

    # 3. 获取所有工单并根据筛选展示
    all_orders = get_recent_orders(limit=50)
    if status_filter != "全部状态":
        filtered_orders = [o for o in all_orders if o["status"] == status_filter]
    else:
        filtered_orders = all_orders

    st.write(f"📋 共检索到 **{len(filtered_orders)}** 条工单：")

    if not filtered_orders:
        st.info("当前筛选条件下无工单数据。")
    else:
        for ord in filtered_orders:
            # 状态标签颜色修饰
            status_badge = {
                "待派工": "🟡 待派工",
                "维修中": "🔵 维修中",
                "已完工": "🟢 已完工"
            }.get(ord["status"], ord["status"])

            with st.expander(f"【{status_badge}】 {ord['order_no']} — {ord['appliance']} ({ord['created_at']})",
                             expanded=(ord["status"] == "待派工")):
                info_col, action_col = st.columns([3, 2])

                with info_col:
                    st.markdown(f"**🏠 客户地址**：{ord['address']}")
                    st.markdown(f"**📞 联系电话**：`{ord['phone']}`")
                    st.markdown(f"**⚠️ 故障描述**：{ord['fault_desc']}")
                    st.caption(f"🆔 关联会话 Session: `{ord.get('session_id', '无')}`")

                with action_col:
                    st.markdown("##### 👷 调度流转操作")
                    current_status = ord["status"]

                    if current_status == "待派工":
                        if st.button(f"🚀 指派师傅出发", key=f"dispatch_{ord['order_no']}", use_container_width=True):
                            update_order_status(ord["order_no"], "维修中")
                            st.success(f"工单 {ord['order_no']} 已转为【维修中】！")
                            st.rerun()

                    elif current_status == "维修中":
                        if st.button(f"✅ 验收核销完工", key=f"finish_{ord['order_no']}", use_container_width=True):
                            update_order_status(ord["order_no"], "已完工")
                            st.success(f"工单 {ord['order_no']} 已成功核销【已完工】！")
                            st.rerun()

                    elif current_status == "已完工":
                        st.success("🎉 该工单已履约闭环完成")

                # 4. 🌟 主管随时回溯此单的完整 AI 问诊病历
                session_id = ord.get("session_id", "default")
                chat_logs = get_session_chat_logs(session_id)
                with st.expander("🔍 调阅此工单的完整 AI 排查问诊流水", expanded=False):
                    if not chat_logs:
                        st.caption("该工单暂无关联的会话问诊明细（可能是历史测试单）。")
                    else:
                        for log in chat_logs:
                            icon = "👤" if log["role"] == "user" else "🤖"
                            role_name = "客户" if log["role"] == "user" else "AI 专家"
                            st.markdown(f"**{icon} {role_name}** (`{log['created_at'][11:]}`):")
                            st.markdown(f"> {log['content']}")