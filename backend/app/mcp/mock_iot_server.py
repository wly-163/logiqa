"""N2 Mock WMS/IoT MCP Server：示例外部 MCP server，提供仓储设备遥测查询。

作为独立进程运行（python -m app.mcp.mock_iot_server），验证 MCP client
发现→注册→调用链路完整性。真实 WMS/IoT 接入时替换 handler 即可。

提供工具：
- query_telemetry(device_id): 返回模拟遥测（温度/库存/任务状态）
"""
import datetime
import random

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Mock WMS/IoT MCP Server", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 模拟仓储设备遥测数据
_MOCK_DEVICES: dict[str, dict] = {
    "cold_storage_01": {"name": "冷链库A", "type": "cold_storage"},
    "asrs_a01": {"name": "A区立体库", "type": "asrs"},
    "agv_01": {"name": "AGV-01", "type": "agv"},
    "dock_out_01": {"name": "发运月台1号", "type": "dock"},
    "temp_sensor_01": {"name": "冷链温控探头1", "type": "temperature_sensor"},
    "hazmat_storage_01": {"name": "危品库1号", "type": "hazmat_storage"},
}

MOCK_TOOLS: list[dict] = [
    {
        "name": "query_telemetry",
        "description": "查询仓储设备实时遥测（温度/库存/任务状态），模拟 WMS/IoT 接口。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "设备 ID，如 cold_storage_01 / agv_01"},
            },
            "required": ["device_id"],
        },
    },
]


def _gen_telemetry(device_id: str) -> dict:
    """生成模拟 WMS/IoT 遥测数据（带随机波动）。"""
    dev = _MOCK_DEVICES.get(device_id, {"name": device_id, "type": "unknown"})
    dtype = dev.get("type", "")
    if dtype == "cold_storage" or "temp" in device_id or "cold" in device_id:
        temperature = round(random.uniform(-22, -15), 1)
    elif dtype == "hazmat_storage":
        temperature = round(random.uniform(15, 28), 1)
    else:
        temperature = round(random.uniform(18, 32), 1)

    task_states = ["idle", "moving", "picking", "charging", "docking", "completed"]
    return {
        "deviceId": device_id,
        "deviceName": dev["name"],
        "deviceType": dtype,
        "temperature": temperature,  # ℃
        "humidity": round(random.uniform(35, 75), 1),  # %
        "inventoryQty": random.randint(0, 5000),  # 件/SKU
        "skuCount": random.randint(0, 800),
        "taskStatus": random.choice(task_states),
        "utilization": round(random.uniform(0.4, 0.98), 2),  # 利用率
        "status": "running",
        "timestamp": datetime.datetime.now().isoformat(),
    }


def _format_telemetry(data: dict) -> str:
    """格式化遥测数据为 LLM 可读文本。"""
    return (
        f"设备: {data['deviceName']} ({data['deviceId']})\n"
        f"类型: {data['deviceType']}\n"
        f"温度: {data['temperature']} ℃\n"
        f"湿度: {data['humidity']} %\n"
        f"库存数量: {data['inventoryQty']} 件\n"
        f"SKU 数: {data['skuCount']}\n"
        f"任务状态: {data['taskStatus']}\n"
        f"利用率: {data['utilization']}\n"
        f"状态: {data['status']}\n"
        f"时间: {data['timestamp']}"
    )


@app.get("/mcp/tools/list")
async def list_tools():
    """列出 mock server 提供的 MCP tools。"""
    return {"tools": MOCK_TOOLS}


@app.post("/mcp/tools/list")
async def list_tools_post():
    """MCP HTTP 传输协议：POST list_tools。"""
    return {"tools": MOCK_TOOLS}


@app.post("/mcp/tools/call")
async def call_tool(request: Request):
    """调用 mock MCP tool。

    Body: {"name": "query_telemetry", "arguments": {"device_id": "cold_storage_01"}}
    """
    body = await request.json()
    name = body.get("name", "")
    args = body.get("arguments", {}) or {}

    if name == "query_telemetry":
        device_id = args.get("device_id", "")
        if not device_id:
            return {"result": "缺少 device_id 参数"}
        data = _gen_telemetry(device_id)
        return {"result": _format_telemetry(data)}
    else:
        return {"result": f"未知工具: {name}"}


@app.get("/health")
async def health():
    """健康检查。"""
    return {"status": "ok", "server": "mock_iot"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9100)
