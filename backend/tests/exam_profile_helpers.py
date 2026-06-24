from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import StudentExamProfile
from app.seed_exam_majors import seed_exam_majors


def add_complete_exam_profile(
    db: Session,
    student_user_id: uuid.UUID,
    *,
    subject_codes: list[str] | None = None,
) -> None:
    seed_exam_majors(db)
    db.add(
        StudentExamProfile(
            user_id=student_user_id,
            major_category_code="academic_master",
            major_code="cs_academic",
            subject_codes=subject_codes or ["english", "math", "politics"],
            profile_completed_at=datetime.now(timezone.utc),
        )
    )
