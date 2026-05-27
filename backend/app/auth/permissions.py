import uuid
from collections.abc import Iterable

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.models import StaffStudent
from app.models.user import User, UserRole


def require_roles(*roles: UserRole):
    allowed: tuple[UserRole, ...] = tuple(roles)

    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient role")
        return user

    return _dep


def require_admin():
    return require_roles(UserRole.org_admin)


def require_staff_or_admin():
    return require_roles(UserRole.org_admin, UserRole.org_staff)


def require_any(roles: Iterable[UserRole]):
    return require_roles(*roles)


def assert_can_access_student(db: Session, actor: User, student_id: uuid.UUID) -> User:
    student = db.get(User, student_id)
    if student is None or student.role != UserRole.student:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "student not found")

    if student.org_id != actor.org_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "cross-org access denied")

    if actor.role == UserRole.org_admin:
        return student

    if actor.role == UserRole.student:
        if actor.id == student.id:
            return student
        raise HTTPException(status.HTTP_403_FORBIDDEN, "students may only access themselves")

    if actor.role == UserRole.org_staff:
        linked = db.execute(
            select(StaffStudent).where(
                StaffStudent.staff_user_id == actor.id,
                StaffStudent.student_user_id == student.id,
            )
        ).scalar_one_or_none()
        if linked is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "student not assigned to staff")
        return student

    raise HTTPException(status.HTTP_403_FORBIDDEN, "role cannot access students")
