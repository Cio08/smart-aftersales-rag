from typing import List,Dict,Any

class SessionMemory:
    """简单的内存会话记忆管理器"""
    def __init__(self, max_history_turns: int = 3):
        # 字典存储所有用户的历史：key 是 session_id, value 是消息列表
        self._store:Dict[str, List[Dict[str, str]]] = {}
        # 默认只保留最近 3 轮（6 条消息），也就是我们刚才讨论的滑动窗口！
        self.max_messages = max_history_turns * 2

    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        """获取指定用户的最近历史对话"""
        return self._store.get(session_id, [])

    def add_turn(self, session_id: str, user_query: str, assistant_reply: str):
        """记录一轮完整的问答，并自动执行滑动窗口截断"""
        if session_id not in self._store:
            self._store[session_id] = []

        # 追加本轮的一问一答
        self._store[session_id].append({"role": "user", "content": user_query})
        self._store[session_id].append({"role": "assistant", "content": assistant_reply})

        # 核心：使用负数切片 [-6:]，永远只保留最近的最新对话，防止撑爆上下文！
        if len(self._store[session_id]) > self.max_messages:
            self._store[session_id] = self._store[session_id][-self.max_messages:]

# 单例导出供全项目使用
session_memory = SessionMemory(max_history_turns=3)