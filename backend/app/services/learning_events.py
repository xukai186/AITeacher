from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models import LearningEvent


class LearningEventService:
    @staticmethod
    def record(
        db: Session,
        *,
        student_user_id: uuid.UUID,
        event_type: str,
        subject_code: str | None = None,
        ref_type: str | None = None,
        ref_id: uuid.UUID | None = None,
        payload: dict | None = None,
    ) -> LearningEvent:
        event = LearningEvent(
            student_user_id=student_user_id,
            subject_code=subject_code,
            event_type=event_type,
            ref_type=ref_type,
            ref_id=ref_id,
            payload_json=payload or {},
        )
        db.add(event)
        db.flush()
        return event
