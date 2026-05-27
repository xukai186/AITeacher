import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class StaffCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=6, max_length=200)


class StaffSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    name: str


class StaffAssignmentRequest(BaseModel):
    staff_user_id: uuid.UUID


class StaffAssignmentOut(BaseModel):
    student_id: uuid.UUID
    staff_user_ids: list[uuid.UUID]
