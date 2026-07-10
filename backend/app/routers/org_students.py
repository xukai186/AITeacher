import uuid
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from app.auth.permissions import assert_can_access_student, require_staff_or_admin
from app.database import get_db
from app.models import User
from app.schemas.org_student import (
    MasterPlanBudgetPatchIn,
    MasterPlanVersionOut,
    OrgStudentOverviewOut,
    OrgStudentPlansOut,
    OrgPaperSummaryOut,
    PaperActionOut,
)
from app.schemas.roadmap import RoadmapRegenerateOut, StudyRoadmapStateOut, StudyRoadmapVersionOut
from app.schemas.task import TodayTasksOut
from app.schemas.wrong_book import WrongBookItemOut
from app.services.admin_intervention import AdminInterventionService
from app.services.org_student import OrgStudentService
from app.services.roadmap_activation import RoadmapActivationService
from app.services.roadmap_generation_jobs import RoadmapGenerationJobService, kick_roadmap_job
from app.services.wrong_book import WrongBookService

router = APIRouter(prefix="/org/students", tags=["org-students"])


def _student_dep(
    student_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_staff_or_admin()),
) -> User:
    return assert_can_access_student(db, actor, student_id)


@router.get("/{student_id}/overview", response_model=OrgStudentOverviewOut)
def student_overview(
    student: User = Depends(_student_dep),
    db: Session = Depends(get_db),
) -> OrgStudentOverviewOut:
    return OrgStudentService().overview(db, student=student)


@router.get("/{student_id}/plans", response_model=OrgStudentPlansOut)
def student_plans(
    student: User = Depends(_student_dep),
    db: Session = Depends(get_db),
) -> OrgStudentPlansOut:
    return OrgStudentService().plans(db, student=student)


@router.get("/{student_id}/tasks", response_model=TodayTasksOut)
def student_tasks(
    student: User = Depends(_student_dep),
    db: Session = Depends(get_db),
    task_date: date | None = Query(default=None),
) -> TodayTasksOut:
    return OrgStudentService().list_tasks(db, student=student, task_date=task_date)


@router.patch("/{student_id}/plans/master", response_model=MasterPlanVersionOut)
def patch_master_plan(
    payload: MasterPlanBudgetPatchIn,
    student: User = Depends(_student_dep),
    db: Session = Depends(get_db),
    actor: User = Depends(require_staff_or_admin()),
) -> MasterPlanVersionOut:
    return AdminInterventionService().update_master_budget(
        db,
        actor=actor,
        student=student,
        daily_time_budget_json=payload.daily_time_budget_json,
    )


@router.get("/{student_id}/papers", response_model=list[OrgPaperSummaryOut])
def student_papers(
    student: User = Depends(_student_dep),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[OrgPaperSummaryOut]:
    return OrgStudentService().list_papers(db, student=student, limit=limit)


@router.post("/{student_id}/papers/{paper_id}/lock", response_model=PaperActionOut)
def lock_paper(
    paper_id: uuid.UUID,
    student: User = Depends(_student_dep),
    db: Session = Depends(get_db),
    actor: User = Depends(require_staff_or_admin()),
) -> PaperActionOut:
    return AdminInterventionService().lock_paper(
        db, actor=actor, student=student, paper_id=paper_id
    )


@router.post("/{student_id}/papers/{paper_id}/replace", response_model=PaperActionOut)
def replace_paper(
    paper_id: uuid.UUID,
    student: User = Depends(_student_dep),
    db: Session = Depends(get_db),
    actor: User = Depends(require_staff_or_admin()),
) -> PaperActionOut:
    return AdminInterventionService().replace_paper(
        db, actor=actor, student=student, paper_id=paper_id
    )


@router.get("/{student_id}/wrong-book", response_model=list[WrongBookItemOut])
def student_wrong_book(
    student: User = Depends(_student_dep),
    db: Session = Depends(get_db),
    subject_code: str | None = Query(default=None, max_length=40),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[WrongBookItemOut]:
    items = WrongBookService.list_items(
        db,
        student.id,
        subject_code=subject_code,
        limit=limit,
        offset=offset,
    )
    return [WrongBookItemOut.model_validate(i) for i in items]


def _roadmap_state_out(raw: dict) -> StudyRoadmapStateOut:
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


@router.get("/{student_id}/roadmap", response_model=StudyRoadmapStateOut)
def student_roadmap(
    student: User = Depends(_student_dep),
    db: Session = Depends(get_db),
) -> StudyRoadmapStateOut:
    raw = RoadmapActivationService().get_state(db, student_user_id=student.id)
    return _roadmap_state_out(raw)


@router.post("/{student_id}/roadmap/regenerate", response_model=RoadmapRegenerateOut)
def regenerate_student_roadmap(
    student: User = Depends(_student_dep),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> RoadmapRegenerateOut:
    result = RoadmapGenerationJobService().enqueue(db, student_user_id=student.id)
    db.commit()
    if result.created:
        background_tasks.add_task(kick_roadmap_job, result.job_id)
    return RoadmapRegenerateOut(job_id=result.job_id, created=result.created)
