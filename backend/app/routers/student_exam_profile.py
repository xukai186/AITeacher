from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.permissions import require_roles
from app.database import get_db
from app.models import ExamMajor, StudentExamProfile, User, UserRole
from app.routers.admin_exam_profile import _to_out
from app.schemas.exam_profile import ExamProfileOut

router = APIRouter(prefix="/student/exam-profile", tags=["student-exam-profile"])


@router.get("", response_model=ExamProfileOut)
def get_my_exam_profile(
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
) -> ExamProfileOut:
    row = db.execute(
        select(StudentExamProfile, ExamMajor)
        .join(ExamMajor, StudentExamProfile.major_code == ExamMajor.code)
        .where(StudentExamProfile.user_id == student.id)
    ).one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "exam profile not found")
    profile, major = row
    return _to_out(profile, major)
