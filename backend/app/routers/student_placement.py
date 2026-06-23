import uuid

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.auth.permissions import require_roles
from app.database import get_db
from app.models import User, UserRole
from app.schemas.placement import (
    PlacementPaperDetail,
    PlacementPaperSummary,
    PlacementStartIn,
    PlacementStartOut,
    PlacementSubmitIn,
    PlacementSubmitOut,
)
from app.services.placement import PlacementService
from app.services.paper_gen_jobs import PaperGenJobService, kick_paper_gen_job, should_kick_paper_gen_job
from app.models import PlacementPaper

router = APIRouter(prefix="/student/placement", tags=["student-placement"])


@router.post("/start", response_model=PlacementStartOut)
def start_placement(
    background_tasks: BackgroundTasks,
    payload: PlacementStartIn | None = None,
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
) -> PlacementStartOut:
    subject_code = payload.subject_code if payload else None
    out = PlacementService.start(db, student.id, subject_code=subject_code)
    if out.gen_job_id is not None:
        background_tasks.add_task(kick_paper_gen_job, out.gen_job_id)
    return out


@router.get("", response_model=list[PlacementPaperSummary])
def list_placement_papers(
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
) -> list[PlacementPaperSummary]:
    return PlacementService.list_papers(db, student.id)


@router.get("/{paper_id}", response_model=PlacementPaperDetail)
def get_placement_paper(
    paper_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
) -> PlacementPaperDetail:
    paper = db.get(PlacementPaper, paper_id)
    if (
        paper is not None
        and paper.student_user_id == student.id
        and paper.status == "generating"
    ):
        active = PaperGenJobService().get_active_for_paper(
            db, paper_id=paper.id, purpose="placement"
        )
        if active is not None and should_kick_paper_gen_job(active):
            background_tasks.add_task(kick_paper_gen_job, active.id)
    return PlacementService.get_paper(db, student.id, paper_id)


@router.post("/{paper_id}/submit", response_model=PlacementSubmitOut)
def submit_placement(
    paper_id: uuid.UUID,
    payload: PlacementSubmitIn,
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
) -> PlacementSubmitOut:
    return PlacementService.submit(db, student.id, paper_id, payload)
