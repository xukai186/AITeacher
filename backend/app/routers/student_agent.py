import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.permissions import require_roles
from app.database import get_db
from app.models import PlanReviewJob, User, UserRole
from app.schemas.plan_review_job import EnqueuePlanReviewOut, PlanReviewJobOut
from app.services.plan_review_jobs import PlanReviewJobService

router = APIRouter(prefix="/student/agent", tags=["student-agent"])


def _job_to_out(job: PlanReviewJob) -> PlanReviewJobOut:
    result = job.result_json or {}
    warnings = list(result.get("warnings") or [])
    scheduled = result.get("scheduled_minutes")
    budget = result.get("budget_minutes")
    over_budget = False
    if isinstance(scheduled, int) and isinstance(budget, int) and scheduled > budget:
        over_budget = True
    return PlanReviewJobOut(
        id=job.id,
        status=job.status,
        subject_code=job.subject_code,
        target_date=job.target_date,
        trigger=job.trigger,
        attempts=job.attempts,
        last_error=job.last_error,
        result_json=job.result_json,
        created_at=job.created_at,
        updated_at=job.updated_at,
        created_count=result.get("created_count"),
        skipped_count=result.get("skipped_count"),
        scheduled_minutes=scheduled,
        budget_minutes=budget,
        over_budget=over_budget,
        warnings=warnings,
    )


@router.post("/apply-recommendations", response_model=EnqueuePlanReviewOut)
def enqueue_apply_recommendations(
    subject_code: str = Query(..., min_length=1, max_length=40),
    target_date: date | None = Query(None),
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
) -> EnqueuePlanReviewOut:
    day = target_date or (date.today() + timedelta(days=1))
    enqueued = PlanReviewJobService().enqueue(
        db,
        student_user_id=student.id,
        subject_code=subject_code,
        target_date=day,
        trigger="manual_apply",
    )
    job = PlanReviewJobService().get_for_student(
        db, job_id=enqueued.job_id, student_user_id=student.id
    )
    if job is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "job missing after enqueue")
    db.commit()
    return EnqueuePlanReviewOut(
        job_id=job.id,
        created=enqueued.created,
        status=job.status,
        subject_code=job.subject_code,
        target_date=job.target_date,
        trigger=job.trigger,
    )


@router.get("/plan-review-jobs/{job_id}", response_model=PlanReviewJobOut)
def get_plan_review_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
) -> PlanReviewJobOut:
    job = PlanReviewJobService().get_for_student(
        db, job_id=job_id, student_user_id=student.id
    )
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
    return _job_to_out(job)
