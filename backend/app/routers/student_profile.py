import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.permissions import require_roles
from app.database import get_db
from app.models import StudentProfile, StudentSubject, User, UserRole

router = APIRouter(prefix="/student", tags=["student"])


class StudentMeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    name: str
    exam_year: int
    subject_codes: list[str]


@router.get("/me", response_model=StudentMeOut)
def get_me(
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
) -> StudentMeOut:
    profile = db.get(StudentProfile, student.id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "profile missing")
    subjects = db.execute(
        select(StudentSubject.subject_code).where(
            StudentSubject.student_user_id == student.id, StudentSubject.enabled.is_(True)
        )
    ).scalars().all()
    return StudentMeOut(
        id=student.id,
        email=student.email,
        name=student.name,
        exam_year=profile.exam_year,
        subject_codes=list(subjects),
    )
