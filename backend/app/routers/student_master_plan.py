from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.permissions import require_roles
from app.database import get_db
from app.models import User, UserRole
from app.schemas.master_plan import MasterPlanConfirmOut, MasterPlanStateOut, MasterPlanVersionOut
from app.services.master_plan_activation import MasterPlanActivationService

router = APIRouter(prefix="/student/master-plan", tags=["student-master-plan"])


def _state_out(raw: dict) -> MasterPlanStateOut:
    active = raw.get("active_version")
    pending = raw.get("pending_version")
    return MasterPlanStateOut(
        plan_id=raw.get("plan_id"),
        plan_status=raw.get("plan_status"),
        active_version=MasterPlanVersionOut.model_validate(active) if active else None,
        pending_version=MasterPlanVersionOut.model_validate(pending) if pending else None,
        budget_change_ratio=raw.get("budget_change_ratio"),
        requires_confirmation=bool(raw.get("requires_confirmation")),
    )


@router.get("", response_model=MasterPlanStateOut)
def get_master_plan(
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
) -> MasterPlanStateOut:
    raw = MasterPlanActivationService().get_state(db, student_user_id=student.id)
    return _state_out(raw)


@router.post("/confirm", response_model=MasterPlanConfirmOut)
def confirm_master_plan(
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
) -> MasterPlanConfirmOut:
    version = MasterPlanActivationService().confirm_pending(db, student_user_id=student.id)
    db.commit()
    return MasterPlanConfirmOut(active_version=MasterPlanVersionOut.model_validate(version))


@router.post("/reject", status_code=204)
def reject_master_plan(
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
) -> None:
    MasterPlanActivationService().reject_pending(db, student_user_id=student.id)
    db.commit()
