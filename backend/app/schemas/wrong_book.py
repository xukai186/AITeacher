import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
    created_at: datetime

