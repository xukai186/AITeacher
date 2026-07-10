from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.permissions import require_roles
from app.database import get_db
from app.models import User, UserRole
from app.schemas.roadmap import RoadmapConfirmOut, StudyRoadmapStateOut, StudyRoadmapVersionOut
from app.services.roadmap_activation import RoadmapActivationService

router = APIRouter(prefix="/student/roadmap", tags=["student-roadmap"])


def _state_out(raw: dict) -> StudyRoadmapStateOut:
    active = raw.get("active_version")
    pending = raw.get("pending_version")
    job = raw.get("generation_job")
    return StudyRoadmapStateOut(
        roadmap_id=raw.get("roadmap_id"),
        status=raw.get("status"),
        active_version=StudyRoadmapVersionOut.model_validate(active) if active else None,
        pending_version=StudyRoadmapVersionOut.model_validate(pending) if pending else None,
        generation_job=job,
    )


@router.get("", response_model=StudyRoadmapStateOut)
def get_roadmap(
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
) -> StudyRoadmapStateOut:
    raw = RoadmapActivationService().get_state(db, student_user_id=student.id)
    return _state_out(raw)


@router.post("/confirm", response_model=RoadmapConfirmOut)
def confirm_roadmap(
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
) -> RoadmapConfirmOut:
    version = RoadmapActivationService().confirm_pending(db, student_user_id=student.id)
    db.commit()
    return RoadmapConfirmOut(active_version=StudyRoadmapVersionOut.model_validate(version))


@router.post("/reject", status_code=204)
def reject_roadmap(
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
) -> None:
    RoadmapActivationService().reject_pending(db, student_user_id=student.id)
    db.commit()
