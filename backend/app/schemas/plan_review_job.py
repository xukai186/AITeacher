import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class EnqueuePlanReviewOut(BaseModel):
    job_id: uuid.UUID
    created: bool
    status: str
    subject_code: str
    target_date: date
    trigger: str


class PlanReviewJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    subject_code: str
    target_date: date
    trigger: str
    attempts: int = Field(ge=0)
    last_error: str | None = None
    result_json: dict | None = None
    created_at: datetime
    updated_at: datetime

    created_count: int | None = None
    skipped_count: int | None = None
    scheduled_minutes: int | None = None
    budget_minutes: int | None = None
    over_budget: bool = False
    warnings: list[str] = Field(default_factory=list)
