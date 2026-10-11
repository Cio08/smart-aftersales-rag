import sqlite3
from pathlib import Path
from datetime import datetime
import random

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
                created_at TEXT NOT NULL 
            )
        """)
        conn.commit()

def insert_repair_order(appliance: str, phone: str, address: str, fault_desc: str = "未详述") -> dict:
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
            INSERT INTO repair_orders (order_no, appliance, phone, address, fault_desc, status, created_at)
            VALUES (?, ?, ?, ?, ?, '待派工', ?)
        """, (order_no, appliance, phone, address, fault_desc, created_at))
        conn.commit()

    return {
        "order_no": order_no,
        "appliance": appliance,
        "phone": phone,
        "address": address,
        "fault_desc": fault_desc,
        "status": "待派工",
        "created_at": created_at
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


# if __name__ == '__main__':
#     test_order = insert_repair_order(
#         appliance="洗碗机",
#         phone="13800138000",
#         address="顺德容桂大道北1号",
#         fault_desc="E01进水超时"
#     )
#     print("✅ 成功插入工单:", test_order)
#     orders = get_recent_orders()
#     print(f"📊 数据库当前共有 {len(orders)} 条工单")
