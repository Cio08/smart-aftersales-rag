from typing import List, Dict, Any
from app.db.database import save_chat_message, get_recent_chat_messages


class SessionMemory:
    """
    会话记忆管理器 (Cache-Aside 旁路缓存架构)
    - L1 高速缓存：内存字典 self._store，0ms 极速响应，支持滑动窗口截断
    - L2 持久化层：SQLite 数据库，全量持久化归档，服务重启冷启动自动回源
    """

    def __init__(self, max_history_turns: int = 3):
        # 字典存储所有用户的历史：key 是 session_id, value 是消息列表
        self._store: Dict[str, List[Dict[str, str]]] = {}
        # 默认保留最近 3 轮（6 条消息）的滑动窗口
        self.max_messages = max_history_turns * 2

    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        """
        获取指定用户的最近历史对话
        🌟 Cache-Aside 读流程：
        1. 先查 L1 内存缓存，命中则直接返回（0ms）
        2. 若未命中（如服务重启、首次访问），穿透回源查 SQLite，装载进 L1 内存
        """
        if session_id not in self._store:
            # 穿透到数据库拉取最近的 max_messages 条记录
            recent_msgs = get_recent_chat_messages(session_id, limit=self.max_messages)
            self._store[session_id] = recent_msgs

        return self._store[session_id]

    def add_turn(self, session_id: str, user_query: str, assistant_reply: str):
        """
        记录一轮完整的问答，执行滑动窗口截断与双写持久化
        🌟 Cache-Aside 写流程：
        1. 确保内存中已有基础记录（冷启动防覆盖）
        2. 更新 L1 内存缓存（追加并滑动窗口截断 [-max_messages:]）
        3. 写入 L2 数据库永久归档
        """
        if session_id not in self._store:
            self._store[session_id] = get_recent_chat_messages(session_id, limit=self.max_messages)

        # 1. 内存高速缓存更新
        self._store[session_id].append({"role": "user", "content": user_query})
        self._store[session_id].append({"role": "assistant", "content": assistant_reply})

        # 滑动窗口截断：使用负数切片 [-6:]，只保留最新对话
        if len(self._store[session_id]) > self.max_messages:
            self._store[session_id] = self._store[session_id][-self.max_messages:]

        # 2. 数据库永久归档（支持全链路溯源与冷启动复活）
        save_chat_message(session_id, "user", user_query)
        save_chat_message(session_id, "assistant", assistant_reply)

    # type: ignore
    def clear_memory_cache(self, session_id: str = None):
        """
        清空 L1 内存缓存（仅用于测试冷启动模拟，不删除 SQLite 数据）
        """
        if session_id:
            self._store.pop(session_id, None)
        else:
            self._store.clear()


# 单例导出供全项目使用
session_memory = SessionMemory(max_history_turns=3)