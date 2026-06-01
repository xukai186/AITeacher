from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import StudentSubject
from app.services.completion_rate_review import CompletionRateReviewService
from app.services.plan_review_jobs import PlanReviewJobService


@dataclass
class DailyGenerationSubjectResult:
    student_user_id: uuid.UUID
    subject_code: str
    created_count: int
    skipped_count: int
    error: str | None = None


@dataclass
class DailyGenerationResult:
    target_date: date
    subjects_processed: int = 0
    subjects_failed: int = 0
    total_created: int = 0
    total_skipped: int = 0
    details: list[DailyGenerationSubjectResult] = field(default_factory=list)


class DailyTaskGenerationService:
    """每日 00:05 定时任务：为所有启用科目的学生生成次日计划（PlanReview）。"""

    def run(
        self,
        db: Session,
        *,
        as_of: date | None = None,
        target_date: date | None = None,
    ) -> DailyGenerationResult:
        today = as_of or date.today()
        day = target_date or (today + timedelta(days=1))

        pairs = db.execute(
            select(StudentSubject.student_user_id, StudentSubject.subject_code).where(
                StudentSubject.enabled.is_(True)
            )
        ).all()

        result = DailyGenerationResult(target_date=day)
        enqueue_svc = PlanReviewJobService()

        for student_user_id, subject_code in pairs:
            try:
                enqueue_svc.enqueue(
                    db,
                    student_user_id=student_user_id,
                    subject_code=subject_code,
                    target_date=day,
                    trigger="daily_schedule",
                )
                detail = DailyGenerationSubjectResult(
                    student_user_id=student_user_id,
                    subject_code=subject_code,
                    created_count=0,
                    skipped_count=0,
                )
                result.details.append(detail)
                result.subjects_processed += 1
            except Exception as exc:  # noqa: BLE001 — batch job records per-row errors
                result.subjects_failed += 1
                result.details.append(
                    DailyGenerationSubjectResult(
                        student_user_id=student_user_id,
                        subject_code=subject_code,
                        created_count=0,
                        skipped_count=0,
                        error=str(exc),
                    )
                )

        CompletionRateReviewService().run_for_all_enabled(
            db, as_of=today, target_date=day
        )
        db.commit()
        return result
