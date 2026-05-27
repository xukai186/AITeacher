from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.permissions import require_admin
from app.auth.security import hash_password
from app.database import get_db
from app.models import StudentProfile, User, UserRole
from app.schemas.student import StudentCreate, StudentSummary
from app.services.audit import record_audit

router = APIRouter(prefix="/admin/students", tags=["admin-students"])


@router.post("", response_model=StudentSummary, status_code=status.HTTP_201_CREATED)
def create_student(
    payload: StudentCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin()),
) -> StudentSummary:
    existing = db.execute(
        select(User).where(User.org_id == admin.org_id, User.email == payload.email)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "email already used in this org")

    user = User(
        org_id=admin.org_id,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=UserRole.student,
        name=payload.name,
    )
    db.add(user)
    db.flush()
    profile = StudentProfile(
        user_id=user.id, exam_year=payload.exam_year, exam_date=payload.exam_date
    )
    db.add(profile)
    record_audit(
        db,
        actor=admin,
        action="student.create",
        target_type="student",
        target_id=str(user.id),
        after={"email": payload.email, "exam_year": payload.exam_year},
    )
    db.commit()
    db.refresh(profile)

    return StudentSummary(
        id=user.id,
        email=user.email,
        name=user.name,
        exam_year=profile.exam_year,
        exam_date=profile.exam_date,
        package_id=profile.package_id,
    )


@router.get("", response_model=list[StudentSummary])
def list_students(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin()),
) -> list[StudentSummary]:
    rows = db.execute(
        select(User, StudentProfile)
        .join(StudentProfile, StudentProfile.user_id == User.id)
        .where(User.org_id == admin.org_id, User.role == UserRole.student)
        .order_by(User.name)
    ).all()
    return [
        StudentSummary(
            id=user.id,
            email=user.email,
            name=user.name,
            exam_year=profile.exam_year,
            exam_date=profile.exam_date,
            package_id=profile.package_id,
        )
        for user, profile in rows
    ]
