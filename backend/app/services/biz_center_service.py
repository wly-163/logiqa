"""经营中心业务：KPI/日报、风险台账、DataAgent、本体归因、专家与定时任务。"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import BizError
from app.models.alert_disposal import AlertDisposal
from app.models.biz_center import BizDailyReport, BizExpertProfile, BizRiskItem, BizScheduledJob
from app.models.kg_triple import KgTriple
from app.models.persistent_task import PersistentTask
from app.models.persona_config import PersonaConfig
from app.models.realtime_event import ProactiveOpsRun, RealtimeEvent
from app.models.ticket import Ticket, TicketStatus
from app.services.biz_metrics import (
    METRIC_SKILLS,
    answer_metrics,
    classify_risk_text,
    compute_metrics,
    severity_from,
)
from app.services.kg_service import get_graph

BUILTIN_EXPERTS = [
    {
        "id": "gm",
        "name": "厂长/仓配总经理助理",
        "personaKey": "gm",
        "focus": "经营总览、KPI 趋势、资源协调",
        "builtin": True,
    },
    {
        "id": "logistics",
        "name": "物流运营助理",
        "personaKey": "logistics",
        "focus": "干线时效、在途异常、仓配作业",
        "builtin": True,
    },
    {
        "id": "quality",
        "name": "品质/温控助理",
        "personaKey": "quality",
        "focus": "冷链温区、品质风险、整改闭环",
        "builtin": True,
    },
]

OPEN_RISK_STATUSES = ("discovered", "analyzing", "rectifying")
DONE_TICKET = {TicketStatus.COMPLETED, TicketStatus.ARCHIVED}
ISSUED_TICKET = {
    TicketStatus.ISSUED,
    TicketStatus.IN_EXECUTION,
    TicketStatus.COMPLETED,
    TicketStatus.ARCHIVED,
}
CONFIRMED_OPS = {"confirmed", "ticketed", "closed"}
OPEN_ALERT = {"pending", "proposed"}
ROLE_HOME = {
    "admin": "gm",
    "editor": "logistics",
    "operator": "logistics",
    "auditor": "gm",
}


def _now() -> datetime:
    return datetime.now()


def _loads(raw: str | None, default):
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def _enum_val(v) -> str:
    return v.value if hasattr(v, "value") else str(v or "")


def _iso(dt: datetime | None) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else ""


def risk_to_dict(r: BizRiskItem) -> dict[str, Any]:
    return {
        "id": r.id,
        "source": r.source,
        "sourceRef": r.source_ref,
        "category": r.category,
        "severity": r.severity,
        "title": r.title,
        "summary": r.summary,
        "owner": r.owner,
        "status": r.status,
        "recommendation": r.recommendation,
        "experience": r.experience,
        "urgeCount": r.urge_count or 0,
        "lastUrgeAt": _iso(r.last_urge_at),
        "ticketId": r.ticket_id or "",
        "createdAt": _iso(r.created_at),
        "updatedAt": _iso(r.updated_at),
        "closedAt": _iso(r.closed_at),
    }


def expert_to_dict(e: BizExpertProfile) -> dict[str, Any]:
    return {
        "id": e.id,
        "name": e.name,
        "personaKey": e.persona_key,
        "skills": _loads(e.skills_json, []),
        "analysisPrompt": e.analysis_prompt or "",
        "schedule": e.schedule,
        "shared": bool(e.shared),
        "owner": e.owner,
        "builtin": False,
        "createdAt": _iso(e.created_at),
    }


def job_to_dict(j: BizScheduledJob) -> dict[str, Any]:
    return {
        "id": j.id,
        "name": j.name,
        "jobType": j.job_type,
        "frequency": j.frequency,
        "recipients": _loads(j.recipients_json, []),
        "enabled": bool(j.enabled),
        "lastRunAt": _iso(j.last_run_at),
        "lastStatus": j.last_status or "",
        "lastError": j.last_error or "",
        "createdAt": _iso(j.created_at),
    }


async def _count(db: AsyncSession, stmt) -> int:
    return int((await db.execute(stmt)).scalar() or 0)


async def _collect_snapshot(db: AsyncSession, tenant: str) -> dict[str, Any]:
    tickets_total = await _count(
        db, select(func.count()).select_from(Ticket).where(
            Ticket.tenant_id == tenant, Ticket.is_deleted == 0,
        )
    )
    tickets_done = await _count(
        db, select(func.count()).select_from(Ticket).where(
            Ticket.tenant_id == tenant, Ticket.is_deleted == 0,
            Ticket.status.in_(tuple(DONE_TICKET)),
        )
    )
    tickets_issued = await _count(
        db, select(func.count()).select_from(Ticket).where(
            Ticket.tenant_id == tenant, Ticket.is_deleted == 0,
            Ticket.status.in_(tuple(ISSUED_TICKET)),
        )
    )
    cutoff = _now() - timedelta(hours=24)
    tickets_overdue = await _count(
        db, select(func.count()).select_from(Ticket).where(
            Ticket.tenant_id == tenant, Ticket.is_deleted == 0,
            Ticket.status == TicketStatus.IN_EXECUTION,
            Ticket.updated_at < cutoff,
        )
    )
    open_alerts = await _count(
        db, select(func.count()).select_from(AlertDisposal).where(
            AlertDisposal.tenant_id == tenant,
            AlertDisposal.status.in_(tuple(OPEN_ALERT)),
        )
    )
    ops_total = await _count(
        db, select(func.count()).select_from(ProactiveOpsRun).where(
            ProactiveOpsRun.tenant_id == tenant,
        )
    )
    ops_confirmed = await _count(
        db, select(func.count()).select_from(ProactiveOpsRun).where(
            ProactiveOpsRun.tenant_id == tenant,
            ProactiveOpsRun.status.in_(tuple(CONFIRMED_OPS)),
        )
    )
    open_risks = await _count(
        db, select(func.count()).select_from(BizRiskItem).where(
            BizRiskItem.tenant_id == tenant,
            BizRiskItem.status.in_(OPEN_RISK_STATUSES),
        )
    )
    p0_open = await _count(
        db, select(func.count()).select_from(BizRiskItem).where(
            BizRiskItem.tenant_id == tenant,
            BizRiskItem.status.in_(OPEN_RISK_STATUSES),
            BizRiskItem.severity == "P0",
        )
    )

    async def cat_open(cat: str) -> int:
        return await _count(
            db, select(func.count()).select_from(BizRiskItem).where(
                BizRiskItem.tenant_id == tenant,
                BizRiskItem.category == cat,
                BizRiskItem.status.in_(OPEN_RISK_STATUSES),
            )
        )

    warehouse_closed = await _count(
        db, select(func.count()).select_from(BizRiskItem).where(
            BizRiskItem.tenant_id == tenant,
            BizRiskItem.category == "warehouse",
            BizRiskItem.status == "closed",
        )
    )
    return {
        "tickets_total": tickets_total,
        "tickets_done": tickets_done,
        "tickets_issued": tickets_issued,
        "tickets_overdue": tickets_overdue,
        "open_alerts": open_alerts,
        "ops_total": ops_total,
        "ops_confirmed": ops_confirmed,
        "open_risks": open_risks,
        "p0_open": p0_open,
        "in_transit_open": await cat_open("in_transit"),
        "warehouse_open": await cat_open("warehouse"),
        "warehouse_closed": warehouse_closed,
        "delay_open": await cat_open("order_delay"),
        "quality_open": await cat_open("quality"),
    }


def compose_briefing(kpis: list[dict], open_risks: list[dict], expert_key: str = "logistics") -> str:
    """确定性经营简报（不依赖 LLM）。"""
    persona = next((e["name"] for e in BUILTIN_EXPERTS if e["id"] == expert_key), "物流运营助理")
    bad = [k for k in kpis if not k.get("ok")]
    ok = [k for k in kpis if k.get("ok")]
    lines = [f"【{persona}】经营简报 {_now().strftime('%Y-%m-%d')}"]
    if ok:
        bits = "、".join(f"{k['name']} {k['value']}{k['unit']}" for k in ok[:4])
        lines.append(f"达标项：{bits}。")
    if bad:
        bits = "、".join(f"{k['name']} {k['value']}{k['unit']}（目标 {k['target']}）" for k in bad[:4])
        lines.append(f"关注项：{bits}。")
    else:
        lines.append("核心经营指标均达到目标阈值。")
    p0 = [r for r in open_risks if r.get("severity") == "P0"]
    if p0:
        lines.append(f"P0 风险 {len(p0)} 项，建议优先催办：{p0[0].get('title', '')}。")
    elif open_risks:
        lines.append(f"未闭环风险 {len(open_risks)} 项，按严重度跟进整改。")
    else:
        lines.append("当前无未闭环风险，保持巡检节奏。")
    lines.append("管理建议：对未达标指标下钻 DataAgent 问数，P0/P1 风险进入风险中心闭环。")
    return "\n".join(lines)


async def _upsert_risk(
    db: AsyncSession, *, tenant: str, source: str, source_ref: str,
    title: str, summary: str, severity_raw: str, ticket_id: str = "",
    recommendation: str = "",
) -> BizRiskItem:
    row = (await db.execute(
        select(BizRiskItem).where(
            BizRiskItem.tenant_id == tenant,
            BizRiskItem.source == source,
            BizRiskItem.source_ref == source_ref,
        )
    )).scalar_one_or_none()
    if row:
        if row.status == "closed":
            return row
        row.title = title[:256]
        row.summary = summary or row.summary
        if ticket_id:
            row.ticket_id = ticket_id
        return row
    row = BizRiskItem(
        tenant_id=tenant,
        source=source,
        source_ref=source_ref,
        category=classify_risk_text(title, summary),
        severity=severity_from(severity_raw),
        title=(title or "未命名风险")[:256],
        summary=summary or "",
        recommendation=recommendation,
        ticket_id=ticket_id or "",
        status="discovered",
    )
    db.add(row)
    await db.flush()
    return row


async def sync_risks_from_sources(db: AsyncSession, tenant: str) -> int:
    """把告警、实时事件、作业单风险点收敛进统一台账。"""
    created = 0
    alerts = (await db.execute(
        select(AlertDisposal).where(AlertDisposal.tenant_id == tenant)
        .order_by(desc(AlertDisposal.created_at)).limit(80)
    )).scalars().all()
    for a in alerts:
        before = a.id
        rec = ""
        try:
            rec = (_loads(a.diagnosis_json, {}) or {}).get("handling") or a.handling or ""
        except Exception:
            rec = a.handling or ""
        row = await _upsert_risk(
            db, tenant=tenant, source="alert", source_ref=str(a.id),
            title=a.title or "告警", summary=a.summary or "",
            severity_raw=a.severity or "warning",
            ticket_id=a.ticket_id or "", recommendation=rec,
        )
        if a.status in {"closed", "rejected"} and row.status != "closed":
            row.status = "closed"
            row.closed_at = row.closed_at or _now()
        elif a.status in {"confirmed", "ticketed"} and row.status == "discovered":
            row.status = "analyzing"
        if before:
            created += 1
    events = (await db.execute(
        select(RealtimeEvent).where(RealtimeEvent.tenant_id == tenant)
        .order_by(desc(RealtimeEvent.occurred_at)).limit(80)
    )).scalars().all()
    for ev in events:
        await _upsert_risk(
            db, tenant=tenant, source="event", source_ref=ev.id,
            title=ev.title or ev.event_type or "实时事件",
            summary=ev.summary or ev.canonical_device_name or "",
            severity_raw=ev.severity or "warning",
        )
        created += 1
    tickets = (await db.execute(
        select(Ticket).where(
            Ticket.tenant_id == tenant, Ticket.is_deleted == 0,
            Ticket.status.in_((
                TicketStatus.IN_EXECUTION, TicketStatus.ISSUED, TicketStatus.PENDING_REVIEW,
            )),
        ).limit(50)
    )).scalars().all()
    for t in tickets:
        risks = _loads(t.risks, [])
        if not risks and t.status != TicketStatus.IN_EXECUTION:
            continue
        await _upsert_risk(
            db, tenant=tenant, source="ticket", source_ref=t.id,
            title=t.title or t.task or "作业风险",
            summary="；".join(str(x) for x in risks) if risks else (t.task or ""),
            severity_raw="P1" if t.status == TicketStatus.IN_EXECUTION else "P2",
            ticket_id=t.id,
        )
        created += 1
    await db.commit()
    return created


async def list_risks(
    db: AsyncSession, tenant: str, *, category: str = "", status: str = "",
    severity: str = "", page: int = 1, size: int = 20,
) -> dict[str, Any]:
    await sync_risks_from_sources(db, tenant)
    stmt = select(BizRiskItem).where(BizRiskItem.tenant_id == tenant)
    cnt = select(func.count()).select_from(BizRiskItem).where(BizRiskItem.tenant_id == tenant)
    if category:
        stmt = stmt.where(BizRiskItem.category == category)
        cnt = cnt.where(BizRiskItem.category == category)
    if status:
        stmt = stmt.where(BizRiskItem.status == status)
        cnt = cnt.where(BizRiskItem.status == status)
    if severity:
        stmt = stmt.where(BizRiskItem.severity == severity)
        cnt = cnt.where(BizRiskItem.severity == severity)
    total = await _count(db, cnt)
    rows = (await db.execute(
        stmt.order_by(desc(BizRiskItem.created_at)).offset((page - 1) * size).limit(size)
    )).scalars().all()
    by_cat = (await db.execute(
        select(BizRiskItem.category, func.count()).where(BizRiskItem.tenant_id == tenant)
        .group_by(BizRiskItem.category)
    )).all()
    open_n = await _count(
        db, select(func.count()).select_from(BizRiskItem).where(
            BizRiskItem.tenant_id == tenant, BizRiskItem.status.in_(OPEN_RISK_STATUSES),
        )
    )
    closed_n = await _count(
        db, select(func.count()).select_from(BizRiskItem).where(
            BizRiskItem.tenant_id == tenant, BizRiskItem.status == "closed",
        )
    )
    health = max(0.0, round(100 - min(100, open_n * 4), 1))
    return {
        "total": total,
        "list": [risk_to_dict(r) for r in rows],
        "byCategory": {c: n for c, n in by_cat},
        "openCount": open_n,
        "closedCount": closed_n,
        "closeRate": round(100.0 * closed_n / (open_n + closed_n), 1) if (open_n + closed_n) else 100.0,
        "healthScore": health,
        "categories": ["warehouse", "in_transit", "quality", "order_delay", "equipment"],
    }


async def get_risk(db: AsyncSession, tenant: str, risk_id: str) -> dict[str, Any]:
    r = (await db.execute(
        select(BizRiskItem).where(BizRiskItem.id == risk_id, BizRiskItem.tenant_id == tenant)
    )).scalar_one_or_none()
    if not r:
        raise BizError("风险不存在", 404)
    stages = [
        {"key": "discovered", "label": "发现风险", "done": True},
        {"key": "analyzing", "label": "详情分析", "done": r.status in ("analyzing", "rectifying", "closed")},
        {"key": "rectifying", "label": "整改跟进", "done": r.status in ("rectifying", "closed")},
        {"key": "closed", "label": "风险闭环", "done": r.status == "closed"},
    ]
    return {**risk_to_dict(r), "stages": stages}


async def update_risk(db: AsyncSession, tenant: str, risk_id: str, body) -> dict[str, Any]:
    r = (await db.execute(
        select(BizRiskItem).where(BizRiskItem.id == risk_id, BizRiskItem.tenant_id == tenant)
    )).scalar_one_or_none()
    if not r:
        raise BizError("风险不存在", 404)
    allowed = {"discovered", "analyzing", "rectifying", "closed"}
    if body.status:
        if body.status not in allowed:
            raise BizError("非法状态", 400)
        r.status = body.status
        if body.status == "closed":
            r.closed_at = _now()
    if body.owner is not None:
        r.owner = body.owner[:64]
    if body.recommendation is not None:
        r.recommendation = body.recommendation
    if body.experience is not None:
        r.experience = body.experience
    await db.commit()
    return await get_risk(db, tenant, risk_id)


async def urge_risk(db: AsyncSession, tenant: str, risk_id: str, username: str, note: str = "") -> dict[str, Any]:
    r = (await db.execute(
        select(BizRiskItem).where(BizRiskItem.id == risk_id, BizRiskItem.tenant_id == tenant)
    )).scalar_one_or_none()
    if not r:
        raise BizError("风险不存在", 404)
    if r.status == "closed":
        raise BizError("已闭环风险不可催办", 400)
    r.urge_count = (r.urge_count or 0) + 1
    r.last_urge_at = _now()
    if note:
        r.summary = (r.summary + f"\n[催办 {username}] {note}").strip()
    if r.status == "discovered":
        r.status = "analyzing"
    await db.commit()
    return risk_to_dict(r)


async def apply_similar(db: AsyncSession, tenant: str, risk_id: str) -> dict[str, Any]:
    """举一反三：把经验复制到同类开放风险。"""
    r = (await db.execute(
        select(BizRiskItem).where(BizRiskItem.id == risk_id, BizRiskItem.tenant_id == tenant)
    )).scalar_one_or_none()
    if not r:
        raise BizError("风险不存在", 404)
    exp = (r.experience or r.recommendation or "").strip()
    if not exp:
        raise BizError("请先填写治理建议或经验沉淀", 400)
    others = (await db.execute(
        select(BizRiskItem).where(
            BizRiskItem.tenant_id == tenant,
            BizRiskItem.category == r.category,
            BizRiskItem.id != r.id,
            BizRiskItem.status.in_(OPEN_RISK_STATUSES),
        ).limit(20)
    )).scalars().all()
    n = 0
    for o in others:
        if not o.recommendation:
            o.recommendation = exp
            n += 1
        if not o.experience:
            o.experience = f"举一反三自「{r.title}」"
    await db.commit()
    return {"applied": n, "category": r.category}


async def overview(db: AsyncSession, tenant: str, role: str = "operator", expert_key: str = "") -> dict[str, Any]:
    await sync_risks_from_sources(db, tenant)
    key = expert_key or ROLE_HOME.get(role, "logistics")
    snap = await _collect_snapshot(db, tenant)
    kpis = compute_metrics(snap)
    open_rows = (await db.execute(
        select(BizRiskItem).where(
            BizRiskItem.tenant_id == tenant,
            BizRiskItem.status.in_(OPEN_RISK_STATUSES),
        ).order_by(desc(BizRiskItem.created_at)).limit(8)
    )).scalars().all()
    open_dicts = [risk_to_dict(x) for x in open_rows]
    insights = compose_briefing(kpis, open_dicts, key)
    return {
        "expertKey": key,
        "experts": BUILTIN_EXPERTS,
        "kpis": kpis,
        "insights": insights,
        "openRisks": open_dicts,
        "snapshot": snap,
        "roleHome": ROLE_HOME.get(role, "logistics"),
    }


async def get_or_create_daily_report(
    db: AsyncSession, tenant: str, expert_key: str = "logistics",
) -> dict[str, Any]:
    day = _now().strftime("%Y-%m-%d")
    row = (await db.execute(
        select(BizDailyReport).where(
            BizDailyReport.tenant_id == tenant,
            BizDailyReport.report_date == day,
            BizDailyReport.expert_key == expert_key,
        )
    )).scalar_one_or_none()
    ov = await overview(db, tenant, expert_key=expert_key)
    insights = ov["insights"]
    risk_summary = f"未闭环 {len(ov['openRisks'])} 项"
    if row:
        row.kpis_json = json.dumps(ov["kpis"], ensure_ascii=False)
        row.insights = insights
        row.risk_summary = risk_summary
    else:
        row = BizDailyReport(
            tenant_id=tenant, report_date=day, expert_key=expert_key,
            kpis_json=json.dumps(ov["kpis"], ensure_ascii=False),
            insights=insights, risk_summary=risk_summary,
        )
        db.add(row)
    await db.commit()
    return {
        "date": day,
        "expertKey": expert_key,
        "kpis": ov["kpis"],
        "insights": insights,
        "riskSummary": risk_summary,
        "openRisks": ov["openRisks"],
    }


async def ask_data_agent(db: AsyncSession, tenant: str, query: str) -> dict[str, Any]:
    await sync_risks_from_sources(db, tenant)
    snap = await _collect_snapshot(db, tenant)
    data = answer_metrics(query, snap)
    data["catalogSize"] = len(METRIC_SKILLS)
    return data


def list_metric_catalog() -> list[dict[str, Any]]:
    return [
        {k: s[k] for k in ("id", "name", "category", "unit", "definition", "target", "keywords")}
        for s in METRIC_SKILLS
    ]


async def capability_map(db: AsyncSession, tenant: str) -> dict[str, Any]:
    experts = list(BUILTIN_EXPERTS)
    custom = (await db.execute(
        select(BizExpertProfile).where(
            BizExpertProfile.tenant_id == tenant,
            or_(BizExpertProfile.shared.is_(True), BizExpertProfile.shared == True),  # noqa: E712
        )
    )).scalars().all()
    modules = [
        {"id": "assistant", "name": "AI经营助理", "desc": "日报、KPI、角色切换"},
        {"id": "risk", "name": "AI风险中心", "desc": "台账、催办、发现到闭环"},
        {"id": "analysis", "name": "专题分析 / DataAgent", "desc": f"{len(METRIC_SKILLS)} 项指标技能问数"},
        {"id": "ontology", "name": "本体归因", "desc": "左图右聊 · 推理链路"},
        {"id": "agentOps", "name": "Agent 协同运营", "desc": "任务调度 · 健康监控 · 专家配置"},
    ]
    return {
        "modules": modules,
        "skills": list_metric_catalog(),
        "experts": experts + [expert_to_dict(e) for e in custom],
        "skillCount": len(METRIC_SKILLS),
    }


def _pick_entity(query: str, triples: list[KgTriple]) -> str:
    names: list[str] = []
    for t in triples:
        names.extend([t.subject, t.object])
    uniq = sorted({n for n in names if n}, key=len, reverse=True)
    for n in uniq:
        if n and n in query:
            return n
    return uniq[0] if uniq else query[:32]


async def ontology_ask(
    db: AsyncSession, tenant: str, query: str, entity: str = "", limit: int = 80,
) -> dict[str, Any]:
    graph = await get_graph(db, entity or "", limit, tenant=tenant)
    like = f"%{(entity or query)[:40]}%"
    rows = (await db.execute(
        select(KgTriple).where(or_(KgTriple.subject.like(like), KgTriple.object.like(like)))
        .limit(40)
    )).scalars().all()
    if not rows:
        rows = (await db.execute(select(KgTriple).limit(30))).scalars().all()
    focus = entity.strip() or _pick_entity(query, rows)
    steps = []
    for i, t in enumerate(rows[:12], 1):
        steps.append({
            "step": i,
            "subject": t.subject,
            "relation": t.relation,
            "object": t.object,
            "owlClass": "Entity",
            "objectProperty": t.relation,
        })
    node_names = {n.get("name") or n.get("id") for n in graph.get("nodes") or []}
    open_risks = (await db.execute(
        select(BizRiskItem).where(
            BizRiskItem.tenant_id == tenant,
            BizRiskItem.status.in_(OPEN_RISK_STATUSES),
        ).limit(100)
    )).scalars().all()
    dist = []
    for name in list(node_names)[:20] or [focus]:
        hits = [r for r in open_risks if name and name in ((r.title or "") + (r.summary or ""))]
        dist.append({
            "node": name,
            "openRisks": len(hits),
            "p0": sum(1 for h in hits if h.severity == "P0"),
        })
    dist.sort(key=lambda x: -x["openRisks"])
    answer = (
        f"围绕「{focus}」检索到 {len(steps)} 步本体关系。"
        f"开放风险命中节点 {sum(1 for d in dist if d['openRisks'])} 个。"
    )
    if steps:
        answer += f" 推理起点：{steps[0]['subject']} —{steps[0]['relation']}→ {steps[0]['object']}。"
    return {
        "query": query,
        "entity": focus,
        "graph": graph,
        "steps": steps,
        "distribution": dist[:12],
        "answer": answer,
        "toolsUsed": 2,
    }


async def list_experts(db: AsyncSession, tenant: str, username: str) -> list[dict[str, Any]]:
    rows = (await db.execute(
        select(BizExpertProfile).where(
            BizExpertProfile.tenant_id == tenant,
            or_(BizExpertProfile.owner == username, BizExpertProfile.shared.is_(True)),
        ).order_by(desc(BizExpertProfile.updated_at))
    )).scalars().all()
    return [*BUILTIN_EXPERTS, *[expert_to_dict(e) for e in rows]]


async def upsert_expert(db: AsyncSession, tenant: str, username: str, body) -> dict[str, Any]:
    row = None
    if body.id:
        row = (await db.execute(
            select(BizExpertProfile).where(
                BizExpertProfile.id == body.id, BizExpertProfile.tenant_id == tenant,
            )
        )).scalar_one_or_none()
        if row and row.owner != username:
            raise BizError("只能修改自己创建的专家", 403)
    if not row:
        row = BizExpertProfile(tenant_id=tenant, owner=username)
        db.add(row)
    row.name = body.name
    row.persona_key = body.personaKey or "logistics"
    row.skills_json = json.dumps(body.skills or [], ensure_ascii=False)
    row.analysis_prompt = body.analysisPrompt or ""
    row.schedule = body.schedule or "none"
    row.shared = bool(body.shared)
    await db.commit()
    await db.refresh(row)
    return expert_to_dict(row)


async def delete_expert(db: AsyncSession, tenant: str, username: str, expert_id: str) -> bool:
    row = (await db.execute(
        select(BizExpertProfile).where(
            BizExpertProfile.id == expert_id, BizExpertProfile.tenant_id == tenant,
        )
    )).scalar_one_or_none()
    if not row:
        raise BizError("专家不存在", 404)
    if row.owner != username:
        raise BizError("只能删除自己创建的专家", 403)
    await db.delete(row)
    await db.commit()
    return True


async def list_jobs(db: AsyncSession, tenant: str) -> list[dict[str, Any]]:
    rows = (await db.execute(
        select(BizScheduledJob).where(BizScheduledJob.tenant_id == tenant)
        .order_by(desc(BizScheduledJob.created_at))
    )).scalars().all()
    return [job_to_dict(j) for j in rows]


async def upsert_job(db: AsyncSession, tenant: str, body) -> dict[str, Any]:
    row = None
    if body.id:
        row = (await db.execute(
            select(BizScheduledJob).where(
                BizScheduledJob.id == body.id, BizScheduledJob.tenant_id == tenant,
            )
        )).scalar_one_or_none()
    if not row:
        row = BizScheduledJob(tenant_id=tenant)
        db.add(row)
    row.name = body.name
    row.job_type = body.jobType or "briefing"
    row.frequency = body.frequency or "daily"
    row.recipients_json = json.dumps(body.recipients or [], ensure_ascii=False)
    row.enabled = bool(body.enabled)
    await db.commit()
    await db.refresh(row)
    return job_to_dict(row)


async def run_job(db: AsyncSession, tenant: str, job_id: str, expert_key: str = "logistics") -> dict[str, Any]:
    row = (await db.execute(
        select(BizScheduledJob).where(
            BizScheduledJob.id == job_id, BizScheduledJob.tenant_id == tenant,
        )
    )).scalar_one_or_none()
    if not row:
        raise BizError("任务不存在", 404)
    try:
        if row.job_type == "risk_scan":
            n = await sync_risks_from_sources(db, tenant)
            payload = {"synced": n}
        else:
            payload = await get_or_create_daily_report(db, tenant, expert_key)
        row.last_run_at = _now()
        row.last_status = "succeeded"
        row.last_error = ""
        await db.commit()
        return {"job": job_to_dict(row), "result": payload}
    except Exception as e:
        row.last_run_at = _now()
        row.last_status = "failed"
        row.last_error = str(e)[:500]
        await db.commit()
        raise


async def agent_health(db: AsyncSession, tenant: str) -> dict[str, Any]:
    by_status = (await db.execute(
        select(PersistentTask.status, func.count()).where(PersistentTask.tenant_id == tenant)
        .group_by(PersistentTask.status)
    )).all()
    status_map = {s: n for s, n in by_status}
    personas = (await db.execute(select(PersonaConfig))).scalars().all()
    ops = (await db.execute(
        select(ProactiveOpsRun.status, func.count()).where(ProactiveOpsRun.tenant_id == tenant)
        .group_by(ProactiveOpsRun.status)
    )).all()
    queued = int(status_map.get("queued") or 0)
    running = int(status_map.get("running") or 0)
    failed = int(status_map.get("failed") or 0) + int(status_map.get("dead") or 0)
    succeeded = int(status_map.get("succeeded") or 0)
    total = queued + running + failed + succeeded
    score = 100.0 if total == 0 else round(100 * succeeded / max(total, 1) - failed * 5, 1)
    agents = [
        {"id": "data", "name": "DataAgent", "status": "healthy" if failed < 3 else "degraded"},
        {"id": "ops", "name": "主动运维 Agent", "status": "healthy"},
        {"id": "quality", "name": "品质整改 Agent", "status": "healthy"},
    ]
    return {
        "score": max(0.0, min(100.0, score)),
        "tasks": status_map,
        "opsRuns": {s: n for s, n in ops},
        "personas": [{"name": p.name, "enabled": bool(p.enabled)} for p in personas],
        "agents": agents,
        "queueDepth": queued + running,
    }
