"""经营中心：风险台账、日报快照、专家配置、定时任务。"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid() -> str:
    return uuid.uuid4().hex


class BizRiskItem(Base):
    """统一风险台账：发现 → 分析 → 整改 → 闭环。"""

    __tablename__ = "biz_risk_item"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source", "source_ref", name="uq_biz_risk_source"),
        Index("ix_biz_risk_tenant_status", "tenant_id", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    source: Mapped[str] = mapped_column(String(24), default="manual")  # alert/event/ticket/scan/manual
    source_ref: Mapped[str] = mapped_column(String(128), default="")
    category: Mapped[str] = mapped_column(String(32), default="warehouse", index=True)
    severity: Mapped[str] = mapped_column(String(8), default="P2", index=True)
    title: Mapped[str] = mapped_column(String(256), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    owner: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(24), default="discovered", index=True)
    recommendation: Mapped[str] = mapped_column(Text, default="")
    experience: Mapped[str] = mapped_column(Text, default="")
    urge_count: Mapped[int] = mapped_column(Integer, default=0)
    last_urge_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ticket_id: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(),
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class BizExpertProfile(Base):
    """个人经营专家：技能组合 + 分析 Prompt + 共享控权。"""

    __tablename__ = "biz_expert_profile"
    __table_args__ = (
        Index("ix_biz_expert_tenant_owner", "tenant_id", "owner"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    owner: Mapped[str] = mapped_column(String(64), default="")
    name: Mapped[str] = mapped_column(String(64), default="")
    persona_key: Mapped[str] = mapped_column(String(32), default="logistics")
    skills_json: Mapped[str] = mapped_column(Text, default="[]")
    analysis_prompt: Mapped[str] = mapped_column(Text, default="")
    schedule: Mapped[str] = mapped_column(String(16), default="none")
    shared: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(),
    )


class BizScheduledJob(Base):
    """经营任务：分析 → 预警 → 推送。"""

    __tablename__ = "biz_scheduled_job"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    job_type: Mapped[str] = mapped_column(String(32), default="briefing")
    frequency: Mapped[str] = mapped_column(String(16), default="daily")
    recipients_json: Mapped[str] = mapped_column(Text, default="[]")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[str] = mapped_column(String(24), default="")
    last_error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class BizDailyReport(Base):
    """经营日报快照（按日幂等）。"""

    __tablename__ = "biz_daily_report"
    __table_args__ = (
        UniqueConstraint("tenant_id", "report_date", "expert_key", name="uq_biz_report_day"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    report_date: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    expert_key: Mapped[str] = mapped_column(String(32), default="logistics")
    kpis_json: Mapped[str] = mapped_column(Text, default="[]")
    insights: Mapped[str] = mapped_column(Text, default="")
    risk_summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
