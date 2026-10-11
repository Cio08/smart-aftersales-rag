import json
from app.db.database import insert_repair_order

# 申报给大模型的工具规格说明书（JSON Schema）
TOOLS_DEFINITION = [
    {
        "type": "function",
        "function": {
            "name": "book_repair_technician",
            "description": "为用户预约专业维修师傅上门检测或维修家电。当用户表达想要报修、预约师傅、派工等意图，并提供了家电品类、联系电话、服务地址时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "appliance": {
                        "type": "string",
                        "description": "需要维修的家电品类，例如：洗碗机、电饭煲、油烟机、空调等"
                    },
                    "phone": {
                        "type": "string",
                        "description": "用户的联系手机号（11位有效号码）"
                    },
                    "address": {
                        "type": "string",
                        "description": "用户的详细上门服务地址（包括街道、小区、门牌号）"
                    },
                    "fault_desc": {
                        "type": "string",
                        "description": "故障的简要描述或错误代码，例如：E01进水超时、不通电、底部漏水等"
                    }
                },
                "required": ["appliance", "phone", "address"]
            }
        }
    }
]

# 2. 本地工具派发器：根据大模型的指令动态调用对应函数
def dispatch_tool(tool_name: str, arguments: dict) -> str:
    """接收大模型的调用请求，执行本地业务逻辑并返回结果字符串"""
    if tool_name == "book_repair_technician":
        # 真正写入 SQLite 数据库
        order = insert_repair_order(
            appliance=arguments.get("appliance", "未知家电"),
            phone=arguments.get("phone", "未提供"),
            address=arguments.get("address", "未提供"),
            fault_desc=arguments.get("fault_desc", "用户未详述")
        )

        # 返回结构化的回执信息给大模型
        return (
            f"【工单系统派工成功回执】\n"
            f"工单编号: {order['order_no']}\n"
            f"报修家电: {order['appliance']}\n"
            f"报修故障: {order['fault_desc']}\n"
            f"联系电话: {order['phone']}\n"
            f"服务地址: {order['address']}\n"
            f"当前状态: 已派工待师傅联系\n"
            f"请告知用户预约已成功，并提醒保持电话畅通。"
        )

    return f"错误：未找到名为 {tool_name} 的本地工具。"