import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MasterPlanVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    source: str
    weekly_goals_json: list[dict] | None
    daily_time_budget_json: list[dict] | None
    created_at: datetime


class MasterPlanStateOut(BaseModel):
    plan_id: uuid.UUID | None = None
    plan_status: str | None = None
    active_version: MasterPlanVersionOut | None = None
    pending_version: MasterPlanVersionOut | None = None
    budget_change_ratio: float | None = Field(
        default=None,
        description="Pending vs active total daily minutes change ratio (0-1+).",
    )
    requires_confirmation: bool = False


class MasterPlanConfirmOut(BaseModel):
    active_version: MasterPlanVersionOut
    message: str = "计划已生效"
