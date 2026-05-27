from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.permissions import require_admin
from app.auth.security import hash_password
from app.database import get_db
from app.models import User, UserRole
from app.schemas.staff import StaffCreate, StaffSummary
from app.services.audit import record_audit

router = APIRouter(prefix="/admin/staff", tags=["admin-staff"])


@router.post("", response_model=StaffSummary, status_code=status.HTTP_201_CREATED)
def create_staff(
    payload: StaffCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin()),
) -> StaffSummary:
    existing = db.execute(
        select(User).where(User.org_id == admin.org_id, User.email == payload.email)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "email already used in this org")
    user = User(
        org_id=admin.org_id,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=UserRole.org_staff,
        name=payload.name,
    )
    db.add(user)
    db.flush()
    record_audit(
        db,
        actor=admin,
        action="staff.create",
        target_type="staff",
        target_id=str(user.id),
        after={"email": payload.email},
    )
    db.commit()
    db.refresh(user)
    return StaffSummary(id=user.id, email=user.email, name=user.name)


@router.get("", response_model=list[StaffSummary])
def list_staff(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin()),
) -> list[StaffSummary]:
    rows = db.execute(
        select(User)
        .where(User.org_id == admin.org_id, User.role == UserRole.org_staff)
        .order_by(User.name)
    ).scalars().all()
    return [StaffSummary(id=r.id, email=r.email, name=r.name) for r in rows]
