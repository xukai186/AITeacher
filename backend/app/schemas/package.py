import uuid

from pydantic import BaseModel, ConfigDict, Field


class PackageCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    subject_codes: list[str] = Field(min_length=1)


class PackageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    subject_codes: list[str]


class AssignPackageRequest(BaseModel):
    package_id: uuid.UUID
