from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel


class QuestionBankCreate(BaseModel):
    scope: Literal["org", "global"]
    org_id: uuid.UUID | None
    subject_code: str
    knowledge_node_id: uuid.UUID | None = None
    q_type: str
    stem: str
    choices_json: list[dict] | None = None
    answer_key: str | None = None
    analysis_text: str | None = None
    difficulty: int | None = None
    source_type: Literal[
        "admin_manual",
        "staff_manual",
        "ocr_import",
        "ai_generated",
    ]
    source_image_asset_id: uuid.UUID | None = None
