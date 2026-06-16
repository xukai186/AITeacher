import uuid

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.permissions import require_roles
from app.database import get_db
from app.models import SelfTestQuestion, User, UserRole
from app.schemas.self_test import (
    SelfTestGenerateIn,
    SelfTestGenerateOut,
    SelfTestGradeOut,
    SelfTestPaperDetailOut,
    SelfTestPaperSummaryOut,
    SelfTestQuestionOut,
    SelfTestSubmitIn,
    SelfTestSubmitOut,
)
from app.services.self_test import SelfTestService
from app.services.paper_gen_jobs import kick_paper_gen_job

router = APIRouter(prefix="/student/self-tests", tags=["student-self-tests"])


@router.post("/generate", response_model=SelfTestGenerateOut)
def generate_self_test(
    payload: SelfTestGenerateIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
) -> SelfTestGenerateOut:
    paper, gen_job_id = SelfTestService.generate(db, student.id, payload.subject_code)
    if gen_job_id is not None:
        background_tasks.add_task(kick_paper_gen_job, gen_job_id)
    return SelfTestGenerateOut(
        id=paper.id,
        subject_code=paper.subject_code,
        status=paper.status,
        created_at=paper.created_at,
        gen_job_id=gen_job_id,
    )


@router.get("", response_model=list[SelfTestPaperSummaryOut])
def list_self_tests(
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
) -> list[SelfTestPaperSummaryOut]:
    papers = SelfTestService.list_papers(db, student.id)
    return [SelfTestPaperSummaryOut.model_validate(p) for p in papers]


@router.get("/{paper_id}", response_model=SelfTestPaperDetailOut)
def get_self_test(
    paper_id: uuid.UUID,
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
) -> SelfTestPaperDetailOut:
    paper = SelfTestService.get_paper(db, student.id, paper_id)
    questions = (
        db.execute(
            select(SelfTestQuestion)
            .where(SelfTestQuestion.paper_id == paper_id)
            .order_by(SelfTestQuestion.seq)
        )
        .scalars()
        .all()
    )
    return SelfTestPaperDetailOut(
        id=paper.id,
        subject_code=paper.subject_code,
        status=paper.status,
        created_at=paper.created_at,
        questions=[
            SelfTestQuestionOut(
                id=q.id,
                seq=q.seq,
                q_type=q.q_type,
                stem=q.stem,
                choices=q.choices_json or [],
                points=q.points,
            )
            for q in questions
        ],
    )


@router.post("/{paper_id}/submit", response_model=SelfTestSubmitOut)
def submit_self_test(
    paper_id: uuid.UUID,
    payload: SelfTestSubmitIn,
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
) -> SelfTestSubmitOut:
    grade = SelfTestService.submit(db, student.id, student.org_id, paper_id, payload)
    return SelfTestSubmitOut(
        submission_id=grade.submission_id,
        total_score=grade.total_score,
        detail_json=grade.detail_json,
    )


@router.get("/submissions/{submission_id}", response_model=SelfTestGradeOut)
def get_self_test_submission_grade(
    submission_id: uuid.UUID,
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
) -> SelfTestGradeOut:
    grade = SelfTestService.get_grade(db, student.id, submission_id)
    return SelfTestGradeOut(
        submission_id=grade.submission_id,
        total_score=grade.total_score,
        detail_json=grade.detail_json,
    )

