import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.permissions import require_roles
from app.database import get_db
from app.models import PaperGenJob, User, UserRole
from app.schemas.paper_gen_job import PaperGenJobOut, PaperGenJobProgress
from app.services.paper_gen_jobs import PaperGenJobRunner, PaperGenJobService

router = APIRouter(prefix="/student/paper-gen-jobs", tags=["student-paper-gen-jobs"])


def _job_to_out(job: PaperGenJob) -> PaperGenJobOut:
    progress_raw = job.progress_json or {}
    progress = PaperGenJobProgress(
        done=int(progress_raw.get("done") or 0),
        total=int(progress_raw.get("total") or 0),
        message=progress_raw.get("message"),
    )
    return PaperGenJobOut(
        id=job.id,
        status=job.status,
        purpose=job.purpose,
        subject_code=job.subject_code,
        paper_id=job.paper_id,
        attempts=job.attempts,
        last_error=job.last_error,
        progress=progress,
        result_json=job.result_json,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get("/{job_id}", response_model=PaperGenJobOut)
def get_paper_gen_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
) -> PaperGenJobOut:
    if PaperGenJobService().get_for_student(db, job_id=job_id, student_user_id=student.id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")

    PaperGenJobRunner().run_pending(db, limit=1, job_id=job_id)
    db.commit()

    job = PaperGenJobService().get_for_student(db, job_id=job_id, student_user_id=student.id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
    return _job_to_out(job)
