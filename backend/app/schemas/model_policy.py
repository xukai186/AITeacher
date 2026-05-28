from typing import Any

from pydantic import BaseModel, Field


class ModelPolicyUpsert(BaseModel):
    scene: str = Field(min_length=1, max_length=40)
    provider: str = Field(min_length=1, max_length=40)
    model: str = Field(min_length=1, max_length=120)
    params: dict[str, Any] = Field(default_factory=dict)


class ModelPolicyOut(ModelPolicyUpsert):
    id: str
    org_id: str
