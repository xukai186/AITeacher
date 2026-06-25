from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import StudentSubject
from app.services.exam_profile import ExamProfileService

ENGLISH_WEIGHTS = {"not_taken": 4, "cet4": 3, "cet6": 2}
MATH_WEIGHTS = {"zero": 4, "basic": 3, "good": 2, "strong": 1}
DEFAULT_ENGLISH = 3
DEFAULT_MATH = 3
POLITICS_BASE = 2


class ExamProfileWeightService:
    def subject_weights(self, db: Session, student_user_id: uuid.UUID) -> dict[str, int]:
        effective = ExamProfileService().get_effective(db, student_user_id)
        if effective is None:
            return {}

        enabled_codes = set(
            db.execute(
                select(StudentSubject.subject_code).where(
                    StudentSubject.student_user_id == student_user_id,
                    StudentSubject.enabled.is_(True),
                )
            )
            .scalars()
            .all()
        )
        if not enabled_codes:
            return {}

        weights: dict[str, int] = {}

        if "english" in enabled_codes:
            weights["english"] = ENGLISH_WEIGHTS.get(
                effective.cet_status, DEFAULT_ENGLISH
            )

        if (
            "math" in enabled_codes
            and effective.math_track != "none"
        ):
            weights["math"] = MATH_WEIGHTS.get(
                effective.math_mastery_level, DEFAULT_MATH
            )

        if "politics" in enabled_codes:
            weights["politics"] = POLITICS_BASE

        return weights
