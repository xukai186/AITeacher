import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class DailyTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    date: date
    subject_code: str
    type: str
    ref_id: uuid.UUID | None
    status: str
    est_minutes: int
    title: str
    created_at: datetime


class TodayTasksOut(BaseModel):
    date: date
    tasks: list[DailyTaskOut]

