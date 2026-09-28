"""经营中心 API：助理/KPI 日报、风险中心、DataAgent、本体归因、Agent 运营。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import DOMAIN_USE
from app.core.response import success
from app.db.session import get_db
from app.dependencies import require_perm
from app.models.user import User
from app.schemas.biz_center import (
    DataAgentAskRequest,
    ExpertUpsertRequest,
    JobUpsertRequest,
    OntologyAskRequest,
    RiskUpdateRequest,
    RiskUrgeRequest,
)
from app.services import biz_center_service as svc

router = APIRouter(prefix="/biz-center", tags=["经营中心"])


@router.get("/overview")
async def overview(
    expertKey: str = "",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_perm(DOMAIN_USE)),
):
    data = await svc.overview(db, user.tenant_id, user.role, expertKey)
    return success(data, "查询成功")


@router.get("/report")
async def daily_report(
    expertKey: str = "logistics",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_perm(DOMAIN_USE)),
):
    data = await svc.get_or_create_daily_report(db, user.tenant_id, expertKey)
    return success(data, "日报已生成")


@router.get("/metrics")
async def metrics_catalog(user: User = Depends(require_perm(DOMAIN_USE))):
    return success(svc.list_metric_catalog(), "查询成功")


@router.post("/data-agent/ask")
async def data_agent_ask(
    body: DataAgentAskRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_perm(DOMAIN_USE)),
):
    data = await svc.ask_data_agent(db, user.tenant_id, body.query)
    return success(data, "问数完成")


@router.get("/capability")
async def capability(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_perm(DOMAIN_USE)),
):
    data = await svc.capability_map(db, user.tenant_id)
    return success(data, "查询成功")


@router.get("/risks")
async def list_risks(
    category: str = "",
    status: str = "",
    severity: str = "",
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_perm(DOMAIN_USE)),
):
    data = await svc.list_risks(
        db, user.tenant_id, category=category, status=status,
        severity=severity, page=page, size=size,
    )
    return success(data, "查询成功")


@router.get("/risks/{risk_id}")
async def get_risk(
    risk_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_perm(DOMAIN_USE)),
):
    data = await svc.get_risk(db, user.tenant_id, risk_id)
    return success(data, "查询成功")


@router.patch("/risks/{risk_id}")
async def update_risk(
    risk_id: str,
    body: RiskUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_perm(DOMAIN_USE)),
):
    data = await svc.update_risk(db, user.tenant_id, risk_id, body)
    return success(data, "已更新")


@router.post("/risks/{risk_id}/urge")
async def urge_risk(
    risk_id: str,
    body: RiskUrgeRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_perm(DOMAIN_USE)),
):
    data = await svc.urge_risk(db, user.tenant_id, risk_id, user.username, body.note)
    return success(data, "已催办")


@router.post("/risks/{risk_id}/apply-similar")
async def apply_similar(
    risk_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_perm(DOMAIN_USE)),
):
    data = await svc.apply_similar(db, user.tenant_id, risk_id)
    return success(data, "已举一反三")


@router.post("/ontology/ask")
async def ontology_ask(
    body: OntologyAskRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_perm(DOMAIN_USE)),
):
    data = await svc.ontology_ask(db, user.tenant_id, body.query, body.entity or "", body.limit)
    return success(data, "归因完成")


@router.get("/experts")
async def list_experts(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_perm(DOMAIN_USE)),
):
    data = await svc.list_experts(db, user.tenant_id, user.username)
    return success(data, "查询成功")


@router.post("/experts")
async def upsert_expert(
    body: ExpertUpsertRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_perm(DOMAIN_USE)),
):
    data = await svc.upsert_expert(db, user.tenant_id, user.username, body)
    return success(data, "已保存")


@router.delete("/experts/{expert_id}")
async def delete_expert(
    expert_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_perm(DOMAIN_USE)),
):
    await svc.delete_expert(db, user.tenant_id, user.username, expert_id)
    return success(True, "已删除")


@router.get("/jobs")
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_perm(DOMAIN_USE)),
):
    return success(await svc.list_jobs(db, user.tenant_id), "查询成功")


@router.post("/jobs")
async def upsert_job(
    body: JobUpsertRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_perm(DOMAIN_USE)),
):
    return success(await svc.upsert_job(db, user.tenant_id, body), "已保存")


@router.post("/jobs/{job_id}/run")
async def run_job(
    job_id: str,
    expertKey: str = "logistics",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_perm(DOMAIN_USE)),
):
    data = await svc.run_job(db, user.tenant_id, job_id, expertKey)
    return success(data, "已执行")


@router.get("/agent-health")
async def agent_health(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_perm(DOMAIN_USE)),
):
    return success(await svc.agent_health(db, user.tenant_id), "查询成功")
