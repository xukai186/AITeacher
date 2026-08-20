from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, model_validator

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


class QuestionBankUpdateRequest(BaseModel):
    stem: str | None = None
    q_type: str | None = None
    choices: list[dict] | None = None
    answer_key: str | None = None
    subject_code: str | None = None
    knowledge_node_id: uuid.UUID | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    analysis_text: str | None = None


class KnowledgeNodeOptionOut(BaseModel):
    id: uuid.UUID
    name: str
    parent_name: str | None = None


class QuestionEnrichmentRequest(BaseModel):
    stem: str
    q_type: str
    choices: list[dict] | None = None
    answer_key: str | None = None


class QuestionEnrichmentOut(BaseModel):
    subject_code: str
    knowledge_node_id: uuid.UUID | None
    knowledge_node_name: str | None = None
    difficulty: int
    analysis_text: str | None
    q_type: str | None


class MediaAssetOut(BaseModel):
    asset_id: uuid.UUID
    storage_key: str


QuestionOCRMode = Literal[
    "single_image_single_question",
    "single_image_multi_question",
    "multi_image_single_question",
]


class QuestionDraftOut(BaseModel):
    q_type: str
    stem: str
    choices: list[dict] | None
    answer_key: str | None


class QuestionOCRRequest(BaseModel):
    mode: QuestionOCRMode | None = None
    asset_id: uuid.UUID | None = None
    asset_ids: list[uuid.UUID] | None = None

    @model_validator(mode="after")
    def normalize_assets(self) -> Self:
        if self.mode is None and self.asset_id is not None:
            self.mode = "single_image_single_question"
            self.asset_ids = [self.asset_id]
            return self
        if self.mode is None:
            raise ValueError("mode or asset_id is required")
        if not self.asset_ids:
            raise ValueError("asset_ids is required")
        if self.mode == "single_image_multi_question" and len(self.asset_ids) != 1:
            raise ValueError("single_image_multi_question requires exactly one asset")
        if self.mode == "multi_image_single_question" and len(self.asset_ids) < 2:
            raise ValueError("multi_image_single_question requires at least two assets")
        if self.mode == "single_image_single_question" and len(self.asset_ids) != 1:
            raise ValueError("single_image_single_question requires exactly one asset")
        return self


class QuestionOCRSegmentedOut(BaseModel):
    mode: Literal["segmented"] = "segmented"
    questions: list[QuestionDraftOut]


class QuestionOCRRawTextFallbackOut(BaseModel):
    mode: Literal["raw_text_fallback"] = "raw_text_fallback"
    raw_text: str


class QuestionOCRSingleQuestionOut(BaseModel):
    mode: Literal["single_question"] = "single_question"
    question: QuestionDraftOut


QuestionOCRResponse = Annotated[
    QuestionOCRSegmentedOut | QuestionOCRRawTextFallbackOut | QuestionOCRSingleQuestionOut,
    Field(discriminator="mode"),
]

# Keep legacy flat shape alias for tests that assert old response during transition:
class QuestionOCROut(QuestionDraftOut):
    pass


class QuestionBankItemOut(BaseModel):
    id: uuid.UUID
    scope: str
    org_id: uuid.UUID | None
    subject_code: str
    knowledge_node_id: uuid.UUID | None
    knowledge_node_name: str | None = None
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
