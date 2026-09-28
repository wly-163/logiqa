"""经营中心请求体。"""
from typing import Optional

from pydantic import BaseModel, Field


class DataAgentAskRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    expertKey: Optional[str] = None


class OntologyAskRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    entity: Optional[str] = None
    limit: int = Field(80, ge=5, le=300)


class RiskUpdateRequest(BaseModel):
    status: Optional[str] = None
    owner: Optional[str] = None
    recommendation: Optional[str] = None
    experience: Optional[str] = None


class RiskUrgeRequest(BaseModel):
    note: str = ""


class ExpertUpsertRequest(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=64)
    personaKey: str = "logistics"
    skills: list[str] = Field(default_factory=list)
    analysisPrompt: str = ""
    schedule: str = "none"
    shared: bool = False


class JobUpsertRequest(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=128)
    jobType: str = "briefing"
    frequency: str = "daily"
    recipients: list[str] = Field(default_factory=list)
    enabled: bool = True
