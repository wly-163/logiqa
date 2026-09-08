"""N3 数字孪生仓储服务测试。

测试重点：
- get_station_layout 加载 rdc-east-demo 模板（24 设备 / 8 区域）
- 状态聚合 riskScore -> 颜色映射（绿->黄->红）
- get_fault_chain 调用 kg_service.get_paths
- push_alert_location 告警定位推送
"""
import asyncio
import datetime

import pytest

from app.services import twin_service
from app.services.twin_service import (
    _color_by_risk,
    _load_layout,
    get_station_layout,
    get_station_overview,
    get_device_detail,
    get_fault_chain,
    push_alert_location,
    DEVICE_TYPES,
)


# ===== _color_by_risk 颜色映射 =====
def test_color_by_risk_zero_is_green():
    """riskScore=0 返回绿色。"""
    color = _color_by_risk(0)
    assert color == "#2ECC71"


def test_color_by_risk_negative_is_green():
    """riskScore<0 也返回绿色（安全兜底）。"""
    color = _color_by_risk(-1)
    assert color == "#2ECC71"


def test_color_by_risk_low_is_green_yellow():
    """riskScore 0-5 之间为绿->黄渐变（HSL hue 120->60）。"""
    color = _color_by_risk(2.5)
    assert color.startswith("hsl(")
    # hue 应在 60-120 之间
    hue = int(color.split("hsl(")[1].split(",")[0])
    assert 60 <= hue <= 120


def test_color_by_risk_medium_is_yellow_orange():
    """riskScore 5-10 之间为黄->橙渐变（HSL hue 60->30）。"""
    color = _color_by_risk(7.5)
    assert color.startswith("hsl(")
    hue = int(color.split("hsl(")[1].split(",")[0])
    assert 30 <= hue <= 60


def test_color_by_risk_high_is_orange_red():
    """riskScore>=10 为橙->红渐变（HSL hue 30->0）。"""
    color = _color_by_risk(15)
    assert color.startswith("hsl(")
    hue = int(color.split("hsl(")[1].split(",")[0])
    assert 0 <= hue <= 30


def test_color_by_risk_very_high_clamped():
    """riskScore 极高值时 hue 不低于 0。"""
    color = _color_by_risk(100)
    hue = int(color.split("hsl(")[1].split(",")[0])
    assert hue >= 0


def test_color_by_risk_monotonic_decreasing_hue():
    """riskScore 递增时 hue 单调递减（绿->黄->橙->红）。"""
    scores = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 20]
    hues = []
    for s in scores:
        c = _color_by_risk(s)
        if c.startswith("hsl("):
            hues.append(int(c.split("hsl(")[1].split(",")[0]))
        else:
            # #2ECC71 = hue 120
            hues.append(120)
    # hue 应单调递减（允许相等）
    for i in range(1, len(hues)):
        assert hues[i] <= hues[i - 1]


# ===== _load_layout 布局加载 =====
def test_load_layout_returns_dict():
    """_load_layout 返回包含 stationId 的字典。"""
    layout = _load_layout("rdc-east-demo")
    assert isinstance(layout, dict)
    assert layout["stationId"] == "rdc-east-demo"
    assert layout["stationName"] == "华东RDC示范仓"


def test_load_layout_has_24_devices():
    """RDC 模板包含约 24 台设备。"""
    layout = _load_layout("rdc-east-demo")
    devices = layout["devices"]
    assert len(devices) == 24


def test_load_layout_has_8_areas():
    """RDC 模板包含 8 个区域。"""
    layout = _load_layout("rdc-east-demo")
    areas = layout["areas"]
    assert len(areas) == 8


def test_load_layout_device_structure():
    """每个设备包含必要字段。"""
    layout = _load_layout("rdc-east-demo")
    for dev in layout["devices"]:
        assert "deviceId" in dev
        assert "name" in dev
        assert "type" in dev
        assert "area" in dev
        assert "position" in dev
        assert "size" in dev
        assert "kgEntity" in dev
        assert "connections" in dev


def test_load_layout_caches_result():
    """_load_layout 第二次调用走缓存（同一对象）。"""
    twin_service._layout_cache.clear()
    first = _load_layout("rdc-east-demo")
    second = _load_layout("rdc-east-demo")
    assert first is second  # 同一对象引用


def test_load_layout_fallback_on_missing_file(monkeypatch):
    """文件不存在时返回空布局兜底。"""
    twin_service._layout_cache.clear()
    from app.config import settings
    monkeypatch.setattr(settings, "TWIN_LAYOUT_PATH", "nonexistent/path.json")
    layout = _load_layout("rdc-east-demo")
    assert layout["areas"] == []
    assert layout["devices"] == []
    twin_service._layout_cache.clear()


# ===== get_station_layout =====
def test_get_station_layout_returns_full_layout():
    """get_station_layout 返回完整布局。"""
    result = asyncio.run(get_station_layout("rdc-east-demo"))
    assert result["stationId"] == "rdc-east-demo"
    assert len(result["devices"]) == 24
    assert len(result["areas"]) == 8


# ===== get_station_overview 状态聚合 =====
def test_get_station_overview_device_count(monkeypatch):
    """get_station_overview 返回所有设备的状态。"""
    async def fake_predict(days=30):
        return {"items": []}
    monkeypatch.setattr("app.services.fault_prediction_service.predict", fake_predict)
    result = asyncio.run(get_station_overview("rdc-east-demo"))
    assert result["deviceCount"] == 24
    assert len(result["devices"]) == 24


def test_get_station_overview_default_risk_zero(monkeypatch):
    """无风险数据时所有设备 riskScore=0（绿色）。"""
    async def fake_predict(days=30):
        return {"items": []}
    monkeypatch.setattr("app.services.fault_prediction_service.predict", fake_predict)
    result = asyncio.run(get_station_overview("rdc-east-demo"))
    for dev in result["devices"]:
        assert dev["riskScore"] == 0
        assert dev["color"] == "#2ECC71"
        assert dev["blink"] is False


def test_get_station_overview_high_risk_blink(monkeypatch):
    """riskScore>=10 的设备 blink=True。"""
    async def fake_predict(days=30):
        return {"items": [{"title": "AGV-01", "riskScore": 15, "riskLevel": "高"}]}
    monkeypatch.setattr("app.services.fault_prediction_service.predict", fake_predict)
    result = asyncio.run(get_station_overview("rdc-east-demo"))
    high_risk = [d for d in result["devices"] if d["riskScore"] >= 10]
    assert len(high_risk) >= 1
    for dev in high_risk:
        assert dev["blink"] is True
        assert dev["alertStatus"] == "active"


def test_get_station_overview_has_generated_at(monkeypatch):
    """overview 包含 generatedAt 时间戳。"""
    async def fake_predict(days=30):
        return {"items": []}
    monkeypatch.setattr("app.services.fault_prediction_service.predict", fake_predict)
    result = asyncio.run(get_station_overview("rdc-east-demo"))
    assert "generatedAt" in result
    assert len(result["generatedAt"]) > 0


def test_get_station_overview_device_has_icon(monkeypatch):
    """每个设备状态包含 icon 字段。"""
    async def fake_predict(days=30):
        return {"items": []}
    monkeypatch.setattr("app.services.fault_prediction_service.predict", fake_predict)
    result = asyncio.run(get_station_overview("rdc-east-demo"))
    for dev in result["devices"]:
        assert "icon" in dev
        assert len(dev["icon"]) > 0


def test_get_station_overview_device_has_model(monkeypatch):
    """每个设备状态包含 model 字段（前端按此选 3D 几何体）。"""
    async def fake_predict(days=30):
        return {"items": []}
    monkeypatch.setattr("app.services.fault_prediction_service.predict", fake_predict)
    result = asyncio.run(get_station_overview("rdc-east-demo"))
    for dev in result["devices"]:
        assert "model" in dev, f"{dev.get('deviceId')} 缺少 model"
        assert isinstance(dev["model"], str)
        assert len(dev["model"]) > 0


def test_get_station_overview_agv_uses_agv_model(monkeypatch):
    """AGV 设备 model == 'agv'。"""
    async def fake_predict(days=30):
        return {"items": []}
    monkeypatch.setattr("app.services.fault_prediction_service.predict", fake_predict)
    result = asyncio.run(get_station_overview("rdc-east-demo"))
    t1 = next(d for d in result["devices"] if d["deviceId"] == "agv_01")
    assert t1["model"] == "agv"


def test_get_station_overview_dock_uses_dock_model(monkeypatch):
    """月台设备 model == 'dock'。"""
    async def fake_predict(days=30):
        return {"items": []}
    monkeypatch.setattr("app.services.fault_prediction_service.predict", fake_predict)
    result = asyncio.run(get_station_overview("rdc-east-demo"))
    cb = next(d for d in result["devices"] if d["deviceId"] == "dock_in_01")
    assert cb["model"] == "dock"


def test_get_station_overview_asrs_uses_asrs_model(monkeypatch):
    """立体库设备 model == 'asrs'。"""
    async def fake_predict(days=30):
        return {"items": []}
    monkeypatch.setattr("app.services.fault_prediction_service.predict", fake_predict)
    result = asyncio.run(get_station_overview("rdc-east-demo"))
    asrs = next(d for d in result["devices"] if d["deviceId"] == "asrs_a01")
    assert asrs["model"] == "asrs"


def test_get_station_overview_cold_storage_model(monkeypatch):
    """冷链库设备 model == 'cold_storage'。"""
    async def fake_predict(days=30):
        return {"items": []}
    monkeypatch.setattr("app.services.fault_prediction_service.predict", fake_predict)
    result = asyncio.run(get_station_overview("rdc-east-demo"))
    cold = next(d for d in result["devices"] if d["deviceId"] == "cold_storage_01")
    assert cold["model"] == "cold_storage"


def test_get_station_overview_has_type_label(monkeypatch):
    """每个设备状态包含 typeLabel（人类可读中文名）。"""
    async def fake_predict(days=30):
        return {"items": []}
    monkeypatch.setattr("app.services.fault_prediction_service.predict", fake_predict)
    result = asyncio.run(get_station_overview("rdc-east-demo"))
    for dev in result["devices"]:
        assert "typeLabel" in dev
        assert isinstance(dev["typeLabel"], str)
        assert len(dev["typeLabel"]) > 0


# ===== DEVICE_TYPES 枚举 =====
def test_device_types_has_agv():
    """DEVICE_TYPES 包含 AGV 类型。"""
    assert "agv" in DEVICE_TYPES
    assert "icon" in DEVICE_TYPES["agv"]
    assert "color" in DEVICE_TYPES["agv"]
    assert "defaultSize" in DEVICE_TYPES["agv"]
    assert "model" in DEVICE_TYPES["agv"]
    assert DEVICE_TYPES["agv"]["model"] == "agv"


def test_device_types_has_dock():
    """DEVICE_TYPES 包含 dock 类型。"""
    assert "dock" in DEVICE_TYPES


def test_device_types_count():
    """DEVICE_TYPES 至少包含 8 种设备类型。"""
    assert len(DEVICE_TYPES) >= 8


def test_device_types_each_has_model():
    """每种设备类型都有 model 字段（前端按此选几何体）。"""
    for type_name, meta in DEVICE_TYPES.items():
        assert "model" in meta, f"{type_name} 缺少 model 字段"
        assert isinstance(meta["model"], str)
        assert len(meta["model"]) > 0


def test_device_types_models_unique():
    """不同设备类型可以使用同一 model，但整体应覆盖多种造型。"""
    models = [meta.get("model") for meta in DEVICE_TYPES.values()]
    # 至少 5 种不同的 model（覆盖 dock/asrs/agv/forklift/sensor 等）
    assert len(set(models)) >= 5


def test_device_types_cold_and_hazmat():
    """包含冷链库与危险品库类型。"""
    assert "cold_storage" in DEVICE_TYPES
    assert "hazmat_storage" in DEVICE_TYPES
    assert DEVICE_TYPES["cold_storage"]["model"] == "cold_storage"
    assert DEVICE_TYPES["hazmat_storage"]["model"] == "hazmat"


# ===== get_fault_chain =====
def test_get_fault_chain_calls_kg_service(monkeypatch):
    """get_fault_chain 调用 kg_service.get_paths。"""
    captured = {}

    async def fake_get_paths(entity, depth=3, limit=10):
        captured["entity"] = entity
        captured["depth"] = depth
        return [{"path": "AGV-01->过载->北巷道"}]

    monkeypatch.setattr("app.services.kg_service.get_paths", fake_get_paths)
    result = asyncio.run(get_fault_chain("agv_01", depth=3))
    assert len(result) == 1
    assert captured["entity"] == "AGV-01"
    assert captured["depth"] == 3


def test_get_fault_chain_unknown_device_returns_empty():
    """未知设备返回空列表。"""
    result = asyncio.run(get_fault_chain("nonexistent_device"))
    assert result == []


def test_get_fault_chain_kg_error_returns_empty(monkeypatch):
    """kg_service 异常时返回空列表（降级不崩）。"""
    async def fake_get_paths(entity, depth=3, limit=10):
        raise RuntimeError("neo4j down")
    monkeypatch.setattr("app.services.kg_service.get_paths", fake_get_paths)
    result = asyncio.run(get_fault_chain("agv_01"))
    assert result == []


# ===== push_alert_location =====
def test_push_alert_location_by_device_id(monkeypatch):
    """通过 deviceId 匹配设备并推送。"""
    pushed = {}

    async def fake_broadcast(msg):
        pushed["msg"] = msg

    monkeypatch.setattr("app.core.ws_manager.broadcast_twin", fake_broadcast)
    result = asyncio.run(push_alert_location({
        "deviceId": "agv_01",
        "severity": "critical",
        "title": "AGV-01库温高",
    }))
    assert result["matched"] is True
    assert result["deviceId"] == "agv_01"
    assert result["pushed"] is True
    assert pushed["msg"]["type"] == "alert"
    assert pushed["msg"]["severity"] == "critical"


def test_push_alert_location_by_name_fuzzy(monkeypatch):
    """通过设备名模糊匹配。"""
    async def fake_broadcast(msg):
        pass
    monkeypatch.setattr("app.core.ws_manager.broadcast_twin", fake_broadcast)
    result = asyncio.run(push_alert_location({
        "device": "AGV-01",
        "severity": "warning",
        "title": "库温告警",
    }))
    assert result["matched"] is True


def test_push_alert_location_no_match(monkeypatch):
    """无法匹配设备时返回 matched=False。"""
    async def fake_broadcast(msg):
        pass
    monkeypatch.setattr("app.core.ws_manager.broadcast_twin", fake_broadcast)
    result = asyncio.run(push_alert_location({
        "device": "不存在的设备",
        "title": "未知告警",
    }))
    assert result["matched"] is False


def test_push_alert_location_ws_error_degraded(monkeypatch):
    """WebSocket 广播异常时降级不崩。"""
    async def fake_broadcast(msg):
        raise ConnectionError("ws down")
    monkeypatch.setattr("app.core.ws_manager.broadcast_twin", fake_broadcast)
    result = asyncio.run(push_alert_location({
        "deviceId": "agv_01",
        "severity": "critical",
    }))
    # 设备匹配成功，但推送可能失败
    assert result["matched"] is True


# ===== get_device_detail =====
def test_get_device_detail_returns_info(monkeypatch):
    """get_device_detail 返回设备详情。"""
    async def fake_graph_context(entity, limit):
        return [{"name": entity, "relation": "connects"}]

    async def fake_get_paths(entity, depth=3, limit=10):
        return [{"path": "agv->aisle"}]

    async def fake_predict(days=30):
        return {"items": [{"title": "AGV-01", "riskScore": 8, "riskLevel": "中", "suggestion": "检查冷机"}]}

    async def fake_list_disposals(page=1, size=5):
        return {"list": []}

    monkeypatch.setattr("app.services.kg_service.graph_context", fake_graph_context)
    monkeypatch.setattr("app.services.kg_service.get_paths", fake_get_paths)
    monkeypatch.setattr("app.services.fault_prediction_service.predict", fake_predict)
    monkeypatch.setattr("app.services.alert_disposal_service.list_disposals", fake_list_disposals)

    result = asyncio.run(get_device_detail("agv_01"))
    assert result["deviceId"] == "agv_01"
    assert result["name"] == "AGV-01"
    assert "kgContext" in result
    assert "faultChain" in result
    assert "riskScore" in result
    assert "alerts" in result


def test_get_device_detail_unknown_device(monkeypatch):
    """未知设备返回 error。"""
    result = asyncio.run(get_device_detail("nonexistent"))
    assert "error" in result
    assert result["deviceId"] == "nonexistent"


def test_get_device_detail_kg_error_degraded(monkeypatch):
    """kg_service 异常时降级返回空列表。"""
    async def fake_graph_context(entity, limit):
        raise RuntimeError("neo4j down")

    async def fake_get_paths(entity, depth=3, limit=10):
        raise RuntimeError("neo4j down")

    async def fake_predict(days=30):
        return {"items": []}

    async def fake_list_disposals(page=1, size=5):
        return {"list": []}

    monkeypatch.setattr("app.services.kg_service.graph_context", fake_graph_context)
    monkeypatch.setattr("app.services.kg_service.get_paths", fake_get_paths)
    monkeypatch.setattr("app.services.fault_prediction_service.predict", fake_predict)
    monkeypatch.setattr("app.services.alert_disposal_service.list_disposals", fake_list_disposals)

    result = asyncio.run(get_device_detail("agv_01"))
    assert result["kgContext"] == []
    assert result["faultChain"] == []
