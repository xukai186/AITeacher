import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReportWeakNodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    knowledge_node_id: uuid.UUID | None
    knowledge_node_name: str | None = None
    wrong_count: int = Field(ge=0)
    total_count: int = Field(ge=0)


class ReportTrendPointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    submission_id: uuid.UUID
    paper_id: uuid.UUID
    subject_code: str
    total_score: int
    created_at: datetime


class ReportOverviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    subject_code: str | None
    wrong_source_counts: dict[str, int]
    weak_nodes: list[ReportWeakNodeOut]
    self_test_trend: list[ReportTrendPointOut]
    recommendations: list[dict] = Field(default_factory=list)

