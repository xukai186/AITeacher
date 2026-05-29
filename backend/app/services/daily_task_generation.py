from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import StudentSubject
from app.services.plan_review import PlanReviewService


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
        review_svc = PlanReviewService()

        for student_user_id, subject_code in pairs:
            try:
                review = review_svc.run_subject_review(
                    db,
                    student_user_id=student_user_id,
                    subject_code=subject_code,
                    trigger="daily_schedule",
                    target_date=day,
                )
                detail = DailyGenerationSubjectResult(
                    student_user_id=student_user_id,
                    subject_code=subject_code,
                    created_count=review.apply.created_count,
                    skipped_count=review.apply.skipped_count,
                )
                result.details.append(detail)
                result.subjects_processed += 1
                result.total_created += review.apply.created_count
                result.total_skipped += review.apply.skipped_count
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

        db.commit()
        return result
