import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PlacementChoiceOut(BaseModel):
    key: str
    text: str


class PlacementQuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    seq: int
    q_type: str
    stem: str
    choices: list[PlacementChoiceOut]
    answer_key: str | None = None


class PlacementPaperSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subject_code: str
    status: str
    title: str
    created_at: datetime


class PlacementPaperDetail(PlacementPaperSummary):
    questions: list[PlacementQuestionOut]


class PlacementSubjectStatus(BaseModel):
    subject_code: str
    status: str
    paper_id: uuid.UUID | None = None


class PlacementStartOut(BaseModel):
    subjects: list[PlacementSubjectStatus]


class PlacementAnswerIn(BaseModel):
    question_id: uuid.UUID
    content: str = Field(min_length=1, max_length=500)


class PlacementSubmitIn(BaseModel):
    answers: list[PlacementAnswerIn]


class PlacementSubmitOut(BaseModel):
    paper_id: uuid.UUID
    total_score: float
    mastery_json: dict[str, Any]
