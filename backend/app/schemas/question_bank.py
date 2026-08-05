from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

QuestionScope = Literal["org", "global"]
QuestionSourceType = Literal[
    "admin_manual",
    "staff_manual",
    "ocr_import",
    "ai_generated",
]


class QuestionBankCreate(BaseModel):
    scope: QuestionScope
    org_id: uuid.UUID | None
    subject_code: str
    knowledge_node_id: uuid.UUID | None = None
    q_type: str
    stem: str
    choices_json: list[dict] | None = None
    answer_key: str | None = None
    analysis_text: str | None = None
    difficulty: int | None = None
    source_type: QuestionSourceType
    source_image_asset_id: uuid.UUID | None = None


class QuestionBankCreateRequest(BaseModel):
    scope: QuestionScope = "org"
    subject_code: str
    knowledge_node_id: uuid.UUID | None = None
    q_type: str
    stem: str
    choices: list[dict] | None = None
    answer_key: str | None = None
    analysis_text: str | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    source_type: QuestionSourceType
    source_image_asset_id: uuid.UUID | None = None


class QuestionEnrichmentRequest(BaseModel):
    stem: str
    q_type: str
    choices: list[dict] | None = None
    answer_key: str | None = None


class QuestionEnrichmentOut(BaseModel):
    subject_code: str
    knowledge_node_id: uuid.UUID | None
    difficulty: int
    analysis_text: str | None
    q_type: str | None


class MediaAssetOut(BaseModel):
    asset_id: uuid.UUID
    storage_key: str


class QuestionOCRRequest(BaseModel):
    asset_id: uuid.UUID


class QuestionOCROut(BaseModel):
    q_type: str
    stem: str
    choices: list[dict] | None
    answer_key: str | None


class QuestionBankItemOut(BaseModel):
    id: uuid.UUID
    scope: str
    org_id: uuid.UUID | None
    subject_code: str
    knowledge_node_id: uuid.UUID | None
    q_type: str
    stem: str
    choices: list[dict] | None
    answer_key: str | None
    analysis_text: str | None
    difficulty: int | None
    source_type: str
    status: str
    created_by: uuid.UUID
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    source_image_asset_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
