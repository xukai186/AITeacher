from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from app.models import PlanReviewJob
from app.services.plan_review import PlanReviewResult, PlanReviewService


@dataclass(frozen=True)
class EnqueueResult:
    job_id: uuid.UUID
    created: bool


class PlanReviewJobService:
    """Persisted job queue for PlanReview (async-ready)."""

    def record_succeeded(
        self,
        db: Session,
        *,
        student_user_id: uuid.UUID,
        subject_code: str,
        target_date: date,
        trigger: str,
        result: PlanReviewResult,
    ) -> uuid.UUID:
        job_id = db.execute(
            select(PlanReviewJob.id).where(
                PlanReviewJob.student_user_id == student_user_id,
                PlanReviewJob.subject_code == subject_code,
                PlanReviewJob.target_date == target_date,
                PlanReviewJob.trigger == trigger,
            )
        ).scalar_one_or_none()

        values = dict(
            status="succeeded",
            locked_at=None,
            last_error=None,
            result_json={
                "subject_code": result.subject_code,
                "target_date": result.target_date.isoformat(),
                "created_count": result.apply.created_count,
                "skipped_count": result.apply.skipped_count,
                "scheduled_minutes": result.trim.scheduled_minutes_after,
                "cancelled_count": result.trim.cancelled_count,
                "warnings": result.warnings,
            },
        )
        if job_id is None:
            job = PlanReviewJob(
                student_user_id=student_user_id,
                subject_code=subject_code,
                target_date=target_date,
                trigger=trigger,
                status="succeeded",
                attempts=1,
                max_attempts=3,
                run_after=datetime.now(timezone.utc),
                locked_at=None,
                last_error=None,
                result_json=values["result_json"],
            )
            db.add(job)
            db.flush()
            return job.id

        db.execute(update(PlanReviewJob).where(PlanReviewJob.id == job_id).values(**values))
        db.flush()
        return job_id

    def enqueue(
        self,
        db: Session,
        *,
        student_user_id: uuid.UUID,
        subject_code: str,
        target_date: date,
        trigger: str,
        run_after: datetime | None = None,
    ) -> EnqueueResult:
        existing = db.execute(
            select(PlanReviewJob.id).where(
                PlanReviewJob.student_user_id == student_user_id,
                PlanReviewJob.subject_code == subject_code,
                PlanReviewJob.target_date == target_date,
                PlanReviewJob.trigger == trigger,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return EnqueueResult(job_id=existing, created=False)

        job = PlanReviewJob(
            student_user_id=student_user_id,
            subject_code=subject_code,
            target_date=target_date,
            trigger=trigger,
            status="pending",
            attempts=0,
            max_attempts=3,
            run_after=run_after or datetime.now(timezone.utc),
            locked_at=None,
            last_error=None,
            result_json=None,
        )
        db.add(job)
        db.flush()
        return EnqueueResult(job_id=job.id, created=True)


class PlanReviewJobRunner:
    """Job runner; can be used by CLI worker or invoked inline."""

    def __init__(self, plan_review: PlanReviewService | None = None) -> None:
        self._plan_review = plan_review or PlanReviewService()

    def run_pending(
        self,
        db: Session,
        *,
        limit: int = 50,
        lock_timeout_seconds: int = 60 * 10,
    ) -> int:
        now = datetime.now(timezone.utc)
        lock_cutoff = now - timedelta(seconds=lock_timeout_seconds)

        stmt = (
            select(PlanReviewJob)
            .where(
                and_(
                    PlanReviewJob.status.in_(("pending", "retry")),
                    PlanReviewJob.run_after <= now,
                    or_(PlanReviewJob.locked_at.is_(None), PlanReviewJob.locked_at < lock_cutoff),
                    PlanReviewJob.attempts < PlanReviewJob.max_attempts,
                )
            )
            .order_by(PlanReviewJob.run_after.asc(), PlanReviewJob.created_at.asc())
            .limit(limit)
        )
        jobs = db.execute(stmt).scalars().all()
        if not jobs:
            return 0

        ran = 0
        for job in jobs:
            # lock
            db.execute(
                update(PlanReviewJob)
                .where(PlanReviewJob.id == job.id)
                .values(status="running", locked_at=now)
            )
            db.flush()

            try:
                result: PlanReviewResult = self._plan_review.run_subject_review(
                    db,
                    student_user_id=job.student_user_id,
                    subject_code=job.subject_code,
                    trigger=job.trigger,
                    target_date=job.target_date,
                )
                db.execute(
                    update(PlanReviewJob)
                    .where(PlanReviewJob.id == job.id)
                    .values(
                        status="succeeded",
                        locked_at=None,
                        attempts=job.attempts + 1,
                        last_error=None,
                        result_json={
                            "subject_code": result.subject_code,
                            "target_date": result.target_date.isoformat(),
                            "created_count": result.apply.created_count,
                            "skipped_count": result.apply.skipped_count,
                            "scheduled_minutes": result.trim.scheduled_minutes_after,
                            "cancelled_count": result.trim.cancelled_count,
                            "warnings": result.warnings,
                        },
                    )
                )
                ran += 1
            except Exception as exc:  # noqa: BLE001
                next_attempt = job.attempts + 1
                failed = next_attempt >= job.max_attempts
                db.execute(
                    update(PlanReviewJob)
                    .where(PlanReviewJob.id == job.id)
                    .values(
                        status="failed" if failed else "retry",
                        locked_at=None,
                        attempts=next_attempt,
                        last_error=str(exc),
                        run_after=now + timedelta(seconds=30),
                    )
                )
                ran += 1

        db.flush()
        return ran

