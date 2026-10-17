import sqlite3
from pathlib import Path
from datetime import datetime
import random
from re import search

# 数据库文件保存在项目的 data 目录下
DB_PATA =Path(__file__).resolve().parent.parent.parent/ "data" / "aftersales.db"

def init_db():
    """初始化数据库与数据表"""
    DB_PATA.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATA) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS repair_orders(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_no TEXT UNIQUE NOT NULL,
                appliance TEXT NOT NULL,
                phone TEXT NOT NULL,
                address TEXT NOT NULL,
                fault_desc TEXT,
                status TEXT DEFAULT '待派工',
                created_at TEXT NOT NULL,
                session_id TEXT DEFAULT 'DEFAULT' 
            )
        """)
        # 新增：会话历史明细表（用于工单全链路溯源）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        # 兼容性小补丁：如果表已存在但没有 session_id 列，自动增加
        cursor.execute("PRAGMA table_info(repair_orders)")
        columns = [col[1] for col in cursor.fetchall()]
        if "session_id" not in columns:
            cursor.execute("ALTER TABLE repair_orders ADD COLUMN session_id TEXT DEFAULT 'default'")
        conn.commit()

def insert_repair_order(appliance: str, phone: str, address: str, fault_desc: str = "未详述", session_id: str = "default") -> dict:
    """插入一条新的报修工单"""
    init_db()       # 确保表已创建

    # 生成一个格式如SHD-20261011-8921 的工单号
    date_str = datetime.now().strftime("%Y%m%d")
    random_code = random.randint(1000, 9999)
    order_no = f"SHD-{date_str}-{random_code}"
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with sqlite3.connect(DB_PATA) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO repair_orders (order_no, appliance, phone, address, fault_desc, status, created_at,session_id)
            VALUES (?, ?, ?, ?, ?, '待派工', ?, ?)
        """, (order_no, appliance, phone, address, fault_desc, created_at, session_id))
        conn.commit()

    return {
        "order_no": order_no,
        "appliance": appliance,
        "phone": phone,
        "address": address,
        "fault_desc": fault_desc,
        "status": "待派工",
        "created_at": created_at,
        "session_id": session_id
    }

def get_recent_orders(limit: int = 10) -> list:
    """获取最新创建的工单列表"""
    init_db()
    with sqlite3.connect(DB_PATA) as conn:
        conn.row_factory = sqlite3.Row  # 让查出的每行数据可以像字典一样用列名访问
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM repair_orders ORDER BY id DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def check_existing_pending_order(phone: str, appliance: str) -> dict | None:
    """
    防重单核心检测：
    查询该手机号名下，同品类电器是否已有处于【待派工】状态的工单
    """
    init_db()
    with sqlite3.connect(DB_PATA) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM repair_orders
            WHERE phone = ? AND appliance = ? AND status = '待派工'
            ORDER BY id DESC LIMIT 1
        """,(phone, appliance))
        row = cursor.fetchone()
        return dict(row) if row else None

def query_orders_by_keyword(keyword: str, limit: int = 5) -> list:
    """
    工单综合查询：
    支持用户根据【手机号】或【工单号】模糊反查进度
    """
    # init_db()
    # with sqlite3.connect(DB_PATA) as conn:
    #     conn.row_factory = sqlite3.Row
    #     cursor = conn.cursor()
    #     search_pattern = f"%{keyword.strip()}%"
    #     cursor.execute("""
    #         SELECT * FROM repair_orders
    #         WHERE order_no LIKE ? OR phone LIKE ?
    #         ORDER BY ID DESC LIMIT ?
    #     """, (search_pattern, search_pattern, limit))
    #     rows =cursor.fetchall()
    #     return [dict(row) for row in rows ]
    init_db()
    with sqlite3.connect(DB_PATA) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        search_pattern = f"%{keyword.strip()}%"
        cursor.execute("""
               SELECT * FROM repair_orders 
               WHERE order_no LIKE ? OR phone LIKE ?
               ORDER BY id DESC LIMIT ?
           """, (search_pattern, search_pattern, limit))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def save_chat_message(session_id: str, role: str, content: str):
    """持久化保存一条聊天记录"""
    init_db()
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_PATA) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO chat_messages (session_id, role, content, created_at)
            VALUES (?, ?, ?, ?)
        """, (session_id, role, content, created_at))
        conn.commit()


def get_recent_chat_messages(session_id: str, limit: int = 6) -> list:
    """
    获取某个会话最近的 N 条聊天消息（按时间升序排列）
    🌟 核心：专供 SessionMemory 内存冷启动/缓存穿透时回源兜底
    采用子查询倒序截取最新 N 条，外层升序还原时间线
    """
    init_db()
    with sqlite3.connect(DB_PATA) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT role, content FROM (
                SELECT id, role, content 
                FROM chat_messages 
                WHERE session_id = ? 
                ORDER BY id DESC 
                LIMIT ?
            ) ORDER BY id ASC
        """, (session_id, limit))
        rows = cursor.fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in rows]


def get_distinct_sessions(limit: int = 15) -> list:
    """获取最近活跃的会话列表，供前端切换历史会话"""
    init_db()
    with sqlite3.connect(DB_PATA) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT session_id, MAX(created_at) as last_active, COUNT(id) as msg_count
            FROM chat_messages
            GROUP BY session_id
            ORDER BY last_active DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def get_session_chat_logs(session_id: str) -> list:
    """根据 session_id 提取该次会话的所有聊天历史（用于排查溯源）"""
    init_db()
    with sqlite3.connect(DB_PATA) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT role, content, created_at 
            FROM chat_messages 
            WHERE session_id = ? 
            ORDER BY id ASC
        """, (session_id,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def get_orders_statistics() -> dict:
    """统计各类状态的工单数量（用于主管看板 KPI 呈现）"""
    init_db()
    with sqlite3.connect(DB_PATA) as conn:
        cursor = conn.cursor()
        # 统计总数
        cursor.execute("SELECT COUNT(*) FROM repair_orders")
        total = cursor.fetchone()[0]

        # 统计待派工
        cursor.execute("SELECT COUNT(*) FROM repair_orders WHERE status = '待派工'")
        pending = cursor.fetchone()[0]

        # 统计维修中
        cursor.execute("SELECT COUNT(*) FROM repair_orders WHERE status = '维修中'")
        processing = cursor.fetchone()[0]

        # 统计已完工
        cursor.execute("SELECT COUNT(*) FROM repair_orders WHERE status = '已完工'")
        completed = cursor.fetchone()[0]

        return {
            "total": total,
            "pending": pending,
            "processing": processing,
            "completed": completed
        }


def update_order_status(order_no: str, new_status: str) -> bool:
    """主管调度操作：修改工单状态（如：待派工 -> 维修中 -> 已完工）"""
    init_db()
    with sqlite3.connect(DB_PATA) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE repair_orders 
            SET status = ? 
            WHERE order_no = ?
        """, (new_status, order_no))
        conn.commit()
        # cursor.rowcount 表示本次 SQL 实际影响/修改了多少行
        return cursor.rowcount > 0


if __name__ == '__main__':
    # 测试统计
    stats = get_orders_statistics()
    print("📊 当前工单统计:", stats)