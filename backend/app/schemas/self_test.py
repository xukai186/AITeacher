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

