"""领域增强 schema：异常诊断 / 相似案例 / 作业单生成。"""
from typing import Optional

from pydantic import BaseModel


class DiagnoseRequest(BaseModel):
    symptom: str                     # 异常症状描述
    modelType: Optional[str] = None


class SimilarCaseRequest(BaseModel):
    symptom: str                     # 当前异常/症状
    modelType: Optional[str] = None


class TicketRequest(BaseModel):
    task: str                        # 作业任务（如"华东仓冷链区温区异常处置"）
    modelType: Optional[str] = None


class TicketAuditRequest(BaseModel):
    ticketText: str                       # 已填票据全文（粘贴）
    ticketType: str = "作业单"             # 作业单 / 运单
    modelType: Optional[str] = None


class DiagnoseAgentRequest(BaseModel):
    symptom: str                        # 异常症状描述
    modelType: Optional[str] = None


class DiagnoseDebateRequest(BaseModel):
    symptom: str                        # 异常症状描述
    modelType: Optional[str] = None


# ===== 作业单/运单全生命周期 =====


class TicketCreateRequest(BaseModel):
    ticketType: str = "作业单"
    task: str = ""
    device: str = ""
    location: str = ""
    steps: list[str] = []
    safety: list[str] = []
    risks: list[str] = []
    notes: str = ""


class TicketListRequest(BaseModel):
    status: str = ""
    ticketType: str = ""
    creator: str = ""
    page: int = 1
    size: int = 20


class TicketReviewRequest(BaseModel):
    approved: bool
    comment: str = ""


class TicketExecuteRequest(BaseModel):
    executor: str = ""
    supervisor: str = ""
    log: str = ""
    deviation: str = ""


# ===== 复杂问题分解 =====


class QueryPlanRequest(BaseModel):
    question: str
    modelType: Optional[str] = None
