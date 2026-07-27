import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    has_explanation: bool = False

    @model_validator(mode="wrap")
    @classmethod
    def _has_explanation_from_orm(cls, data, handler):
        if hasattr(data, "explanation_text"):
            out = handler(data)
            return out.model_copy(
                update={"has_explanation": bool(data.explanation_text)}
            )
        return handler(data)


class WrongBookPracticeIn(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class WrongBookPracticeOut(BaseModel):
    is_correct: bool
    status: str
    consecutive_correct_count: int
    mastered: bool


class WrongBookExplainIn(BaseModel):
    regenerate: bool = False


class WrongBookExplainOut(BaseModel):
    explanation_text: str
    from_cache: bool
    explanation_created_at: datetime | None
