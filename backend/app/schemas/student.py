import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class StudentCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=6, max_length=200)
    exam_year: int = Field(ge=2025, le=2100)
    exam_date: date | None = None


class StudentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    name: str
    exam_year: int
    exam_date: date | None
    package_id: uuid.UUID | None
