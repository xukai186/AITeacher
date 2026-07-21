import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.permissions import require_admin
from app.auth.security import hash_password
from app.database import get_db
from app.models import Package, StaffStudent, StudentProfile, StudentSubject, User, UserRole
from app.schemas.package import AssignPackageRequest
from app.schemas.staff import StaffAssignmentOut, StaffAssignmentRequest
from app.schemas.student import StudentCreate, StudentDetail, StudentSummary
from app.services.audit import record_audit
from app.services.org_student_signals import signals_for_students

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
    student_ids = [user.id for user, _ in rows]
    signals = signals_for_students(db, student_ids)
    staff_by_student: dict[uuid.UUID, list[uuid.UUID]] = {sid: [] for sid in student_ids}
    if student_ids:
        for staff_id, student_id in db.execute(
            select(StaffStudent.staff_user_id, StaffStudent.student_user_id).where(
                StaffStudent.student_user_id.in_(student_ids)
            )
        ).all():
            staff_by_student[student_id].append(staff_id)
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
            staff_user_ids=staff_by_student.get(user.id, []),
        )
        for user, profile in rows
    ]


@router.post("/{student_id}/package", response_model=StudentDetail)
def assign_package(
    student_id: uuid.UUID,
    payload: AssignPackageRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin()),
) -> StudentDetail:
    student = db.get(User, student_id)
    if student is None or student.role != UserRole.student or student.org_id != admin.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "student not found")
    pkg = db.get(Package, payload.package_id)
    if pkg is None or pkg.org_id != admin.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "package not found")

    profile = db.get(StudentProfile, student.id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "profile missing")
    profile.package_id = pkg.id

    existing = {
        row.subject_code
        for row in db.execute(
            select(StudentSubject).where(StudentSubject.student_user_id == student.id)
        ).scalars()
    }
    for code in pkg.subject_codes:
        if code not in existing:
            db.add(StudentSubject(student_user_id=student.id, subject_code=code))

    record_audit(
        db,
        actor=admin,
        action="student.assign_package",
        target_type="student",
        target_id=str(student.id),
        after={"package_id": str(pkg.id), "subjects": pkg.subject_codes},
    )
    db.commit()
    db.refresh(profile)

    return StudentDetail(
        id=student.id,
        email=student.email,
        name=student.name,
        exam_year=profile.exam_year,
        exam_date=profile.exam_date,
        package_id=profile.package_id,
        subject_codes=pkg.subject_codes,
    )


@router.post("/{student_id}/staff", response_model=StaffAssignmentOut)
def assign_staff(
    student_id: uuid.UUID,
    payload: StaffAssignmentRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin()),
) -> StaffAssignmentOut:
    student = db.get(User, student_id)
    if student is None or student.role != UserRole.student or student.org_id != admin.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "student not found")
    staff = db.get(User, payload.staff_user_id)
    if staff is None or staff.role != UserRole.org_staff or staff.org_id != admin.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "staff not found")

    existing = db.execute(
        select(StaffStudent).where(
            StaffStudent.staff_user_id == staff.id, StaffStudent.student_user_id == student.id
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            StaffStudent(
                staff_user_id=staff.id,
                student_user_id=student.id,
                assigned_by_user_id=admin.id,
            )
        )
        record_audit(
            db,
            actor=admin,
            action="student.assign_staff",
            target_type="student",
            target_id=str(student.id),
            after={"staff_user_id": str(staff.id)},
        )
        db.commit()

    rows = db.execute(
        select(StaffStudent.staff_user_id).where(StaffStudent.student_user_id == student.id)
    ).scalars().all()
    return StaffAssignmentOut(student_id=student.id, staff_user_ids=list(rows))


@router.delete("/{student_id}/staff/{staff_user_id}", response_model=StaffAssignmentOut)
def unassign_staff(
    student_id: uuid.UUID,
    staff_user_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin()),
) -> StaffAssignmentOut:
    student = db.get(User, student_id)
    if student is None or student.role != UserRole.student or student.org_id != admin.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "student not found")

    link = db.execute(
        select(StaffStudent).where(
            StaffStudent.staff_user_id == staff_user_id,
            StaffStudent.student_user_id == student.id,
        )
    ).scalar_one_or_none()
    if link is not None:
        db.delete(link)
        record_audit(
            db,
            actor=admin,
            action="student.unassign_staff",
            target_type="student",
            target_id=str(student.id),
            before={"staff_user_id": str(staff_user_id)},
        )
        db.commit()

    rows = db.execute(
        select(StaffStudent.staff_user_id).where(StaffStudent.student_user_id == student.id)
    ).scalars().all()
    return StaffAssignmentOut(student_id=student.id, staff_user_ids=list(rows))
