import json
from app.db.database import (
    insert_repair_order,
    check_existing_pending_order,
    query_orders_by_keyword
)

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
    },
    {
        "type": "function",
        "function": {
            "name": "query_repair_order",
            "description": "查询家电报修工单的最新进度与记录。当用户询问已报修电器的处理进度、想要查单、或提供了手机号/工单号查进度时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "用户的联系手机号（如 13800000000）或工单编号（如 SHD-20261011-3153）"
                    }
                },
                "required": ["keyword"]
            }
        }
    }
]

# 2. 本地工具派发器：根据大模型的指令动态调用对应函数
def dispatch_tool(tool_name: str, arguments: dict, session_id: str = 'default') -> str:
    """接收大模型的调用请求，执行本地业务逻辑并返回结果字符串"""
    # ---------------- 分支 1：预约派单工具 ----------------
    if tool_name == "book_repair_technician":
        # 把接收到的信息存到变量中，查重后再决定是否写入数据库
        appliance=arguments.get("appliance", "未知家电")
        phone=arguments.get("phone", "未提供")
        address=arguments.get("address", "未提供")
        fault_desc=arguments.get("fault_desc", "用户未详述")
        # 🌟 【企业级防重单机制】：先查后下！
        existing = check_existing_pending_order(phone=phone, appliance=appliance)
        if existing:
            return (
                f"【工单系统提示：重复报修拦截】\n"
                f"系统检测到手机号{phone} 名下的【{appliance}】已于{existing['created_at']} 提交过报修申请！\n"
                f"已有工单编号：{existing['order_no']}\n"
                f"报修故障：{existing['fault_desc']}\n"
                f"当前状态：{existing['status']}\n"
                f"服务地址：{existing['address']}\n"
                f"【处理指引】：严禁重复下单！请委婉告知用户无需重复报修，系统已为其做加急催办处理，工程师正在抓紧派工联系中。"
            )

        # 未重复，正常写入SQLite 数据库
        order = insert_repair_order(
            appliance=appliance,
            phone=phone,
            address=address,
            fault_desc=fault_desc,
            session_id=session_id
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

    # ---------------- 分支 2：查单与进度跟踪工具 ----------------
    elif tool_name == "query_repair_order":
        keyword = arguments.get("keyword", "")
        orders = query_orders_by_keyword(keyword=keyword)

        if not orders:
            return  f"【工单系统查询结果】未查询到与关键字 '{keyword}' 相关的报修工单记录。请告知用户核对手机号或工单编号是否输入正确。"

        # 拼接查询到的工单信息给大模型
        lines = [f"【工单系统查询结果】共查询到 {len(orders)} 条关联工单："]
        for o in orders:
            lines.append(
                f"- 工单号: {o['order_no']} | 家电: {o['appliance']} | 状态: {o['status']} | "
                f"故障: {o['fault_desc']} | 服务地址: {o['address']} | 下单时间: {o['created_at']}"
            )
        lines.append("【处理指引】：请向用户清晰汇报查询到的工单编号、当前处理状态、家电及报修时间，态度真诚贴心。")
        return "\n".join(lines)

    return f"错误：未找到名为 {tool_name} 的本地工具。"

if __name__ == "__main__":
    # 实验 A：测试防重单拦截（用你昨天已经下过单的手机号和洗碗机）
    dup_res = dispatch_tool("book_repair_technician", {
        "appliance": "洗碗机",
        "phone": "19203551306",
        "address": "勒流公舍二楼",
        "fault_desc": "又坏了"
    })
    print("🛡️ 防重单拦截测试:\n", dup_res)
    print("=" * 50)

    # 实验 B：测试查单工具
    query_res = dispatch_tool("query_repair_order", {"keyword": "19203551306"})
    print("🔍 查单工具测试:\n", query_res)