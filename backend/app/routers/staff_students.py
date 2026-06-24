from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.permissions import require_roles
from app.database import get_db
from app.models import StaffStudent, StudentProfile, User, UserRole
from app.schemas.student import StudentSummary
from app.services.org_student_signals import signals_for_students

router = APIRouter(prefix="/staff", tags=["staff"])


@router.get("/students", response_model=list[StudentSummary])
def my_students(
    db: Session = Depends(get_db),
    staff: User = Depends(require_roles(UserRole.org_staff)),
) -> list[StudentSummary]:
    rows = db.execute(
        select(User, StudentProfile)
        .join(StudentProfile, StudentProfile.user_id == User.id)
        .join(StaffStudent, StaffStudent.student_user_id == User.id)
        .where(StaffStudent.staff_user_id == staff.id)
        .order_by(User.name)
    ).all()
    student_ids = [user.id for user, _ in rows]
    signals = signals_for_students(db, student_ids)
    return [
        StudentSummary(
            id=user.id,
            email=user.email,
            name=user.name,
            exam_year=profile.exam_year,
            exam_date=profile.exam_date,
            package_id=profile.package_id,
            pending_task_count=signals[user.id].pending_task_count,
            open_review_job_count=signals[user.id].open_review_job_count,
            requires_plan_confirmation=signals[user.id].requires_plan_confirmation,
            wrong_added_7d=signals[user.id].wrong_added_7d,
            exam_profile_complete=signals[user.id].exam_profile_complete,
        )
        for user, profile in rows
    ]
