import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SelfTestGenerateIn(BaseModel):
    subject_code: str = Field(min_length=1, max_length=40)


class SelfTestPaperSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subject_code: str
    status: str
    created_at: datetime


class SelfTestGenerateOut(SelfTestPaperSummaryOut):
    gen_job_id: uuid.UUID | None = None


class SelfTestChoiceOut(BaseModel):
    key: str
    text: str


class SelfTestQuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    seq: int
    q_type: str
    stem: str
    choices: list[SelfTestChoiceOut] = []
    points: int


class SelfTestPaperDetailOut(SelfTestPaperSummaryOut):
    questions: list[SelfTestQuestionOut]


class SelfTestAnswerIn(BaseModel):
    question_id: uuid.UUID
    content: str = Field(min_length=1, max_length=8000)


class SelfTestSubmitIn(BaseModel):
    answers: list[SelfTestAnswerIn]


class SelfTestSubmitOut(BaseModel):
    submission_id: uuid.UUID
    total_score: int
    detail_json: dict


class SelfTestGradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    submission_id: uuid.UUID
    total_score: int
    detail_json: dict

