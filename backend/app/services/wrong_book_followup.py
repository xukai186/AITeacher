from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyTask, WrongBookItem
from app.services.subject_agent import REC_EST_MINUTES, _task_ref_id

REVIEW_DAYS = 3


class WrongBookFollowUpService:
    """批阅后在未来数日插入错题复习任务（规格 §6.5）。"""

    def schedule_after_self_test(
        self,
        db: Session,
        *,
        student_user_id: uuid.UUID,
        subject_code: str,
        submission_id: uuid.UUID,
        base_date: date | None = None,
    ) -> int:
        """为本次提交产生的错题，在 base_date 起连续 REVIEW_DAYS 天各建一条 review_wrong（幂等）。"""
        start = base_date or date.today()
        wrong_items = (
            db.execute(
                select(WrongBookItem)
                .where(
                    WrongBookItem.student_user_id == student_user_id,
                    WrongBookItem.subject_code == subject_code,
                    WrongBookItem.source_type == "self_test",
                    WrongBookItem.source_id == submission_id,
                )
                .order_by(WrongBookItem.created_at)
            )
            .scalars()
            .all()
        )
        if not wrong_items:
            return 0

        node_id = wrong_items[0].knowledge_node_id
        node_key = str(node_id) if node_id else ""
        title = "错题复习（自测巩固）"
        if node_id:
            title = f"错题复习：{wrong_items[0].question_snapshot_json.get('stem', title)[:40]}"

        created = 0
        for offset in range(1, REVIEW_DAYS + 1):
            day = start + timedelta(days=offset)
            ref_id = _task_ref_id(
                student_user_id,
                day,
                subject_code,
                "review_wrong",
                node_key or str(submission_id),
            )
            existing = db.execute(
                select(DailyTask.id).where(
                    DailyTask.student_user_id == student_user_id,
                    DailyTask.date == day,
                    DailyTask.subject_code == subject_code,
                    DailyTask.type == "review_wrong",
                    DailyTask.ref_id == ref_id,
                )
            ).scalar_one_or_none()
            if existing is not None:
                continue

            db.add(
                DailyTask(
                    student_user_id=student_user_id,
                    date=day,
                    subject_code=subject_code,
                    type="review_wrong",
                    ref_id=ref_id,
                    status="pending",
                    est_minutes=REC_EST_MINUTES.get("review_wrong", 30),
                    title=title,
                    payload_json={
                        "source": "self_test_graded",
                        "submission_id": str(submission_id),
                        "knowledge_node_id": node_key or None,
                    },
                )
            )
            created += 1

        db.flush()
        return created
