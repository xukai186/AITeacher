import uuid
from datetime import datetime

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
    choices: list[PlacementChoiceOut] = Field(default_factory=list)
    answer_key: str | None = None
    points: int = 1


class PlacementPaperSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subject_code: str
    status: str
    title: str
    created_at: datetime


class PlacementPaperDetail(PlacementPaperSummary):
    questions: list[PlacementQuestionOut]
    gen_job_id: uuid.UUID | None = None


class PlacementSubjectStatus(BaseModel):
    subject_code: str
    status: str
    paper_id: uuid.UUID | None = None


class PlacementStartIn(BaseModel):
    subject_code: str | None = None


class PlacementStartOut(BaseModel):
    subjects: list[PlacementSubjectStatus]
    gen_job_id: uuid.UUID | None = None


class PlacementAnswerIn(BaseModel):
    question_id: uuid.UUID
    content: str = Field(min_length=1, max_length=10000)


class PlacementSubmitIn(BaseModel):
    answers: list[PlacementAnswerIn]


class PlacementSubmitOut(BaseModel):
    paper_id: uuid.UUID
    total_score: int
    mastery_json: dict
    roadmap_job_id: uuid.UUID | None = None
    all_placement_complete: bool = False
