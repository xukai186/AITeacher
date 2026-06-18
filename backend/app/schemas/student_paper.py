import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class StudentPaperSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    paper_type: Literal["placement", "self_test"]
    subject_code: str
    status: str
    title: str
    created_at: datetime
    submission_id: uuid.UUID | None = None
    total_score: int | None = None
