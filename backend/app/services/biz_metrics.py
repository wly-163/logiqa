"""物流经营指标技能库：口径 + 关键词匹配 + 由快照计数计算。

不依赖数据库，便于单测与 DataAgent 问数。
"""
from __future__ import annotations

from typing import Any

METRIC_SKILLS: list[dict[str, Any]] = [
    {
        "id": "otif",
        "name": "准时达效率 OTIF",
        "category": "delivery",
        "unit": "%",
        "target": 95.0,
        "definition": "已完成作业单 / 已签发作业单。口径近似仓配准时交付，签发后未闭环视为未达。",
        "keywords": ["otif", "准时", "达效", "交付", "时效达成"],
    },
    {
        "id": "ticket_close",
        "name": "作业闭环率",
        "category": "warehouse",
        "unit": "%",
        "target": 90.0,
        "definition": "已完成+已归档作业单 / 作业单总数。衡量作业协同闭环。",
        "keywords": ["闭环", "作业单", "完成率", "归档"],
    },
    {
        "id": "in_transit_exc",
        "name": "在途异常率",
        "category": "in_transit",
        "unit": "%",
        "target": 5.0,
        "invert": True,
        "definition": "在途/干线类未闭环风险 / 未闭环风险总数。",
        "keywords": ["在途", "干线", "异常率", "运输", "tms"],
    },
    {
        "id": "wh_sla",
        "name": "仓配作业时效达成",
        "category": "warehouse",
        "unit": "%",
        "target": 92.0,
        "definition": "仓配类已闭环风险 / 仓配类风险。无仓配风险时按作业闭环率回落。",
        "keywords": ["仓配", "仓库", "sla", "拣货", "上架"],
    },
    {
        "id": "alert_health",
        "name": "风险健康分",
        "category": "risk",
        "unit": "分",
        "target": 90.0,
        "definition": "100 - min(100, 开放告警×8 + P0风险×12 + 逾期作业×6)。",
        "keywords": ["健康分", "风险分", "告警健康"],
    },
    {
        "id": "open_risks",
        "name": "未闭环风险数",
        "category": "risk",
        "unit": "项",
        "target": 0.0,
        "invert": True,
        "definition": "状态非 closed 的风险台账条数。",
        "keywords": ["未闭环", "开放风险", "风险数"],
    },
    {
        "id": "p0_share",
        "name": "P0 风险占比",
        "category": "risk",
        "unit": "%",
        "target": 10.0,
        "invert": True,
        "definition": "未闭环风险中 severity=P0 的占比。",
        "keywords": ["p0", "高危", "严重"],
    },
    {
        "id": "proactive_confirm",
        "name": "主动预警确认率",
        "category": "ops",
        "unit": "%",
        "target": 80.0,
        "definition": "已确认/已转单的主动运维运行 / 主动运维运行总数。",
        "keywords": ["主动预警", "确认率", "proactive"],
    },
    {
        "id": "order_delay",
        "name": "订单延期风险数",
        "category": "order_delay",
        "unit": "项",
        "target": 0.0,
        "invert": True,
        "definition": "分类为订单延期的未闭环风险数。",
        "keywords": ["延期", "逾期订单", "滞后"],
    },
    {
        "id": "quality_risk",
        "name": "品质/温控风险数",
        "category": "quality",
        "unit": "项",
        "target": 0.0,
        "invert": True,
        "definition": "分类为品质/温控的未闭环风险数。",
        "keywords": ["品质", "温控", "冷链", "质量"],
    },
]


def _pct(num: float, den: float) -> float:
    if den <= 0:
        return 0.0
    return round(100.0 * num / den, 2)


def compute_metrics(snap: dict[str, Any]) -> list[dict[str, Any]]:
    """由聚合快照计算全部指标当前值。"""
    tickets_total = int(snap.get("tickets_total") or 0)
    tickets_issued = int(snap.get("tickets_issued") or 0)
    tickets_done = int(snap.get("tickets_done") or 0)
    tickets_overdue = int(snap.get("tickets_overdue") or 0)
    open_alerts = int(snap.get("open_alerts") or 0)
    ops_total = int(snap.get("ops_total") or 0)
    ops_confirmed = int(snap.get("ops_confirmed") or 0)
    open_risks = int(snap.get("open_risks") or 0)
    p0_open = int(snap.get("p0_open") or 0)
    in_transit_open = int(snap.get("in_transit_open") or 0)
    warehouse_open = int(snap.get("warehouse_open") or 0)
    warehouse_closed = int(snap.get("warehouse_closed") or 0)
    delay_open = int(snap.get("delay_open") or 0)
    quality_open = int(snap.get("quality_open") or 0)

    issued_or_done = max(tickets_issued, tickets_done)
    values = {
        "otif": _pct(tickets_done, issued_or_done),
        "ticket_close": _pct(tickets_done, tickets_total),
        "in_transit_exc": _pct(in_transit_open, open_risks),
        "wh_sla": (
            _pct(warehouse_closed, warehouse_open + warehouse_closed)
            if (warehouse_open + warehouse_closed) > 0
            else _pct(tickets_done, tickets_total)
        ),
        "alert_health": max(
            0.0,
            round(100 - min(100, open_alerts * 8 + p0_open * 12 + tickets_overdue * 6), 1),
        ),
        "open_risks": float(open_risks),
        "p0_share": _pct(p0_open, open_risks),
        "proactive_confirm": _pct(ops_confirmed, ops_total),
        "order_delay": float(delay_open),
        "quality_risk": float(quality_open),
    }

    out = []
    for skill in METRIC_SKILLS:
        val = values.get(skill["id"], 0.0)
        target = float(skill.get("target") or 0)
        invert = bool(skill.get("invert"))
        if invert:
            ok = val <= target
        else:
            ok = val >= target
        delta = round(val - target, 2)
        out.append({
            **{k: skill[k] for k in ("id", "name", "category", "unit", "definition", "target")},
            "value": val,
            "ok": ok,
            "delta": delta,
            "invert": invert,
        })
    return out


def match_skills(query: str, top_k: int = 4) -> list[dict[str, Any]]:
    """按关键词命中指标技能，无命中则返回核心 4 项。"""
    q = (query or "").strip().lower()
    scored: list[tuple[int, dict[str, Any]]] = []
    for skill in METRIC_SKILLS:
        score = 0
        if skill["id"] in q or skill["name"].lower() in q:
            score += 8
        for kw in skill["keywords"]:
            if kw.lower() in q:
                score += 3
        if score:
            scored.append((score, skill))
    scored.sort(key=lambda x: -x[0])
    picked = [s for _, s in scored[:top_k]]
    if not picked:
        ids = {"otif", "ticket_close", "alert_health", "open_risks"}
        picked = [s for s in METRIC_SKILLS if s["id"] in ids]
    return picked


def answer_metrics(query: str, snap: dict[str, Any]) -> dict[str, Any]:
    """DataAgent 问数：匹配技能 + 填入当前值 + 口径说明。"""
    metrics = {m["id"]: m for m in compute_metrics(snap)}
    skills = match_skills(query)
    rows = []
    for skill in skills:
        m = metrics.get(skill["id"])
        if not m:
            continue
        rows.append({
            "id": m["id"],
            "name": m["name"],
            "value": m["value"],
            "unit": m["unit"],
            "target": m["target"],
            "ok": m["ok"],
            "delta": m["delta"],
            "definition": m["definition"],
            "category": m["category"],
        })
    return {
        "query": query,
        "skills": [s["id"] for s in skills],
        "rows": rows,
        "note": "指标由作业单、告警、主动预警与风险台账聚合，口径见 definition。",
    }


def classify_risk_text(title: str, summary: str = "") -> str:
    text = f"{title} {summary}".lower()
    rules = [
        ("quality", ("温", "冷链", "品质", "质量", "质检")),
        ("in_transit", ("在途", "干线", "运输", "时效", "tms")),
        ("order_delay", ("延期", "逾期", "滞后", "delay")),
        ("warehouse", ("仓", "拣", "上架", "agv", "立体库", "rdc", "fdc")),
        ("equipment", ("设备", "停机", "振动", "iot")),
    ]
    for cat, kws in rules:
        if any(k in text for k in kws):
            return cat
    return "warehouse"


def severity_from(raw: str) -> str:
    s = (raw or "").lower()
    if s in {"critical", "p0", "fatal", "emergency"}:
        return "P0"
    if s in {"error", "high", "p1", "major"}:
        return "P1"
    return "P2"
