import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WrongBookItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subject_code: str
    knowledge_node_id: uuid.UUID | None
    source_type: str
    source_id: uuid.UUID | None
    question_snapshot_json: dict
    answer_snapshot_json: dict
    correct_snapshot_json: dict
    status: str
    wrong_count: int
    consecutive_correct_count: int
    mastered_at: datetime | None
    last_practice_at: datetime | None
    created_at: datetime


class WrongBookPracticeIn(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class WrongBookPracticeOut(BaseModel):
    is_correct: bool
    status: str
    consecutive_correct_count: int
    mastered: bool
