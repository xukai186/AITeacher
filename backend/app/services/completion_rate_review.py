from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import DailyTask, StudentSubject
from app.services.plan_review_jobs import PlanReviewJobService

COMPLETION_WINDOW_DAYS = 3
COMPLETION_THRESHOLD = 0.6


class CompletionRateReviewService:
    """连续 N 天单科完成率低于阈值时触发计划复审（规格 §6.2）。"""

    def maybe_enqueue_for_student_subject(
        self,
        db: Session,
        *,
        student_user_id: uuid.UUID,
        subject_code: str,
        as_of: date | None = None,
        target_date: date | None = None,
    ) -> bool:
        today = as_of or date.today()
        day = target_date or (today + timedelta(days=1))

        rates: list[float] = []
        for offset in range(COMPLETION_WINDOW_DAYS):
            d = today - timedelta(days=offset)
            total = db.execute(
                select(func.count(DailyTask.id)).where(
                    DailyTask.student_user_id == student_user_id,
                    DailyTask.subject_code == subject_code,
                    DailyTask.date == d,
                    DailyTask.status.in_(("pending", "in_progress", "completed", "skipped")),
                )
            ).scalar_one()
            if not total:
                continue
            done = db.execute(
                select(func.count(DailyTask.id)).where(
                    DailyTask.student_user_id == student_user_id,
                    DailyTask.subject_code == subject_code,
                    DailyTask.date == d,
                    DailyTask.status == "completed",
                )
            ).scalar_one()
            rates.append(done / total)

        if len(rates) < COMPLETION_WINDOW_DAYS:
            return False
        if any(r >= COMPLETION_THRESHOLD for r in rates):
            return False

        PlanReviewJobService().enqueue(
            db,
            student_user_id=student_user_id,
            subject_code=subject_code,
            target_date=day,
            trigger="low_completion_rate",
        )
        return True

    def run_for_all_enabled(
        self,
        db: Session,
        *,
        as_of: date | None = None,
        target_date: date | None = None,
    ) -> int:
        today = as_of or date.today()
        day = target_date or (today + timedelta(days=1))
        pairs = db.execute(
            select(StudentSubject.student_user_id, StudentSubject.subject_code).where(
                StudentSubject.enabled.is_(True)
            )
        ).all()
        enqueued = 0
        for student_user_id, subject_code in pairs:
            if self.maybe_enqueue_for_student_subject(
                db,
                student_user_id=student_user_id,
                subject_code=subject_code,
                as_of=today,
                target_date=day,
            ):
                enqueued += 1
        return enqueued
