"""经营中心：指标技能、简报、分类与 DataAgent 匹配。"""
import sys

import pytest

from app.services.biz_metrics import (
    METRIC_SKILLS,
    answer_metrics,
    classify_risk_text,
    compute_metrics,
    match_skills,
    severity_from,
)


def test_metric_catalog_size():
    assert len(METRIC_SKILLS) >= 8
    ids = {s["id"] for s in METRIC_SKILLS}
    assert {"otif", "ticket_close", "alert_health", "open_risks"} <= ids


def test_compute_otif_and_health():
    snap = {
        "tickets_total": 10,
        "tickets_done": 8,
        "tickets_issued": 10,
        "tickets_overdue": 1,
        "open_alerts": 1,
        "ops_total": 5,
        "ops_confirmed": 4,
        "open_risks": 4,
        "p0_open": 1,
        "in_transit_open": 2,
        "warehouse_open": 1,
        "warehouse_closed": 3,
        "delay_open": 0,
        "quality_open": 1,
    }
    by_id = {m["id"]: m for m in compute_metrics(snap)}
    assert by_id["otif"]["value"] == 80.0
    assert by_id["ticket_close"]["value"] == 80.0
    assert by_id["in_transit_exc"]["value"] == 50.0
    assert by_id["open_risks"]["value"] == 4
    assert by_id["proactive_confirm"]["value"] == 80.0
    assert by_id["alert_health"]["value"] < 100


def test_match_skills_otif():
    picked = match_skills("准时达效率怎么样")
    assert any(s["id"] == "otif" for s in picked)


def test_data_agent_answer_includes_definition():
    snap = {
        "tickets_total": 2, "tickets_done": 1, "tickets_issued": 2, "tickets_overdue": 0,
        "open_alerts": 0, "ops_total": 0, "ops_confirmed": 0, "open_risks": 0, "p0_open": 0,
        "in_transit_open": 0, "warehouse_open": 0, "warehouse_closed": 0,
        "delay_open": 0, "quality_open": 0,
    }
    out = answer_metrics("OTIF 和作业闭环", snap)
    assert out["rows"]
    assert all("definition" in r for r in out["rows"])


def test_classify_and_severity():
    assert classify_risk_text("干线在途延误") == "in_transit"
    assert classify_risk_text("冷链温区超温") == "quality"
    assert classify_risk_text("订单延期未发运") == "order_delay"
    assert severity_from("critical") == "P0"
    assert severity_from("warning") == "P2"


@pytest.mark.skipif(sys.version_info < (3, 11), reason="项目运行时为 3.11+（datetime.UTC）")
@pytest.mark.asyncio
async def test_overview_and_daily_report(test_db):
    from app.services import biz_center_service as svc

    ov = await svc.overview(test_db, "default", "operator")
    assert ov["expertKey"] == "logistics"
    assert len(ov["kpis"]) >= 8
    report = await svc.get_or_create_daily_report(test_db, "default", "logistics")
    assert report["insights"]
    assert report["date"]


@pytest.mark.skipif(sys.version_info < (3, 11), reason="项目运行时为 3.11+（datetime.UTC）")
@pytest.mark.asyncio
async def test_risk_urge_and_apply_similar(test_db):
    from app.models.biz_center import BizRiskItem
    from app.services import biz_center_service as svc

    a = BizRiskItem(
        tenant_id="default", source="manual", source_ref="a",
        category="warehouse", severity="P1", title="拣货延误",
        recommendation="加开波次", status="discovered",
    )
    b = BizRiskItem(
        tenant_id="default", source="manual", source_ref="b",
        category="warehouse", severity="P2", title="上架积压",
        status="discovered",
    )
    test_db.add_all([a, b])
    await test_db.commit()
    urged = await svc.urge_risk(test_db, "default", a.id, "admin", "请处理")
    assert urged["urgeCount"] == 1
    assert urged["status"] == "analyzing"
    applied = await svc.apply_similar(test_db, "default", a.id)
    assert applied["applied"] >= 1


@pytest.mark.skipif(sys.version_info < (3, 11), reason="项目运行时为 3.11+（datetime.UTC）")
def test_compose_briefing_mentions_p0():
    from app.services.biz_center_service import compose_briefing
    kpis = [
        {"name": "准时达效率 OTIF", "value": 80, "unit": "%", "target": 95, "ok": False},
        {"name": "作业闭环率", "value": 96, "unit": "%", "target": 90, "ok": True},
    ]
    risks = [{"severity": "P0", "title": "干线延误"}]
    text = compose_briefing(kpis, risks, "logistics")
    assert "关注项" in text
    assert "P0" in text
    assert "物流运营助理" in text
