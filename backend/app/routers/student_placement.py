import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.permissions import require_roles
from app.database import get_db
from app.models import User, UserRole
from app.schemas.placement import PlacementPaperDetail, PlacementPaperSummary, PlacementStartOut
from app.services.placement import PlacementService

router = APIRouter(prefix="/student/placement", tags=["student-placement"])


@router.post("/start", response_model=PlacementStartOut)
def start_placement(
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
) -> PlacementStartOut:
    return PlacementService.start(db, student.id)


@router.get("", response_model=list[PlacementPaperSummary])
def list_placement_papers(
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
) -> list[PlacementPaperSummary]:
    return PlacementService.list_papers(db, student.id)


@router.get("/{paper_id}", response_model=PlacementPaperDetail)
def get_placement_paper(
    paper_id: uuid.UUID,
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
) -> PlacementPaperDetail:
    return PlacementService.get_paper(db, student.id, paper_id)
