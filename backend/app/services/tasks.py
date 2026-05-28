from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyTask, StudentSubject


class TaskGenerator:
    def generate_next_7_days(self, db: Session, student_user_id: uuid.UUID, today: date) -> None:
        subject_codes = list(
            db.execute(
                select(StudentSubject.subject_code).where(
                    StudentSubject.student_user_id == student_user_id,
                    StudentSubject.enabled.is_(True),
                )
            )
            .scalars()
            .all()
        )
        if not subject_codes:
            return

        subject_code = subject_codes[0]
        for i in range(7):
            day = today + timedelta(days=i)
            db.add(
                DailyTask(
                    student_user_id=student_user_id,
                    date=day,
                    subject_code=subject_code,
                    type="study",
                    ref_id=None,
                    status="pending",
                    est_minutes=60,
                    title="英语 学习任务" if subject_code == "english" else f"{subject_code} 学习任务",
                    payload_json=None,
                )
            )
        db.commit()

