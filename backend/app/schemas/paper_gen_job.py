import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PaperGenJobProgress(BaseModel):
    done: int = 0
    total: int = 0
    message: str | None = None


class PaperGenJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    purpose: str
    subject_code: str
    paper_id: uuid.UUID
    attempts: int
    last_error: str | None = None
    progress: PaperGenJobProgress | None = None
    result_json: dict | None = None
    created_at: datetime
    updated_at: datetime
