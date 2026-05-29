import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.task import DailyTaskOut


class ApplyRecommendationsOut(BaseModel):
    target_date: date
    subject_code: str
    created: list[DailyTaskOut]
    created_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    budget_minutes: int | None = None
    scheduled_minutes: int = Field(ge=0)
    over_budget: bool = False
    warnings: list[str] = Field(default_factory=list)
