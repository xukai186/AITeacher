from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ExamMajor, StudentExamProfile, StudentSubject
from app.schemas.exam_profile import EffectiveExamProfile

KNOWN_SUBJECT_CODES = ("english", "math", "politics")


class ExamProfileService:
    def get_effective(
        self, db: Session, student_user_id: uuid.UUID
    ) -> EffectiveExamProfile | None:
        row = db.execute(
            select(StudentExamProfile, ExamMajor)
            .join(ExamMajor, StudentExamProfile.major_code == ExamMajor.code)
            .where(StudentExamProfile.user_id == student_user_id)
        ).one_or_none()
        if row is None:
            return None

        profile, major = row
        return EffectiveExamProfile(
            major_category_code=profile.major_category_code,
            major_code=profile.major_code,
            major_name=major.name,
            english_track=profile.english_track or major.default_english_track,
            math_track=profile.math_track or major.default_math_track,
            subject_codes=list(profile.subject_codes),
            cet_status=profile.cet_status,
            cet_score=profile.cet_score,
            math_mastery_level=profile.math_mastery_level,
            profile_completed_at=profile.profile_completed_at,
        )

    def sync_student_subjects(
        self, db: Session, student_user_id: uuid.UUID, subject_codes: list[str]
    ) -> None:
        enabled_set = set(subject_codes)
        for code in KNOWN_SUBJECT_CODES:
            row = db.execute(
                select(StudentSubject).where(
                    StudentSubject.student_user_id == student_user_id,
                    StudentSubject.subject_code == code,
                )
            ).scalar_one_or_none()
            enabled = code in enabled_set
            if row is None:
                db.add(
                    StudentSubject(
                        student_user_id=student_user_id,
                        subject_code=code,
                        enabled=enabled,
                    )
                )
            else:
                row.enabled = enabled

    def is_complete(self, db: Session, student_user_id: uuid.UUID) -> bool:
        profile = db.get(StudentExamProfile, student_user_id)
        if profile is None:
            return False
        return profile.profile_completed_at is not None and bool(profile.major_code)

    def get_or_create_profile(
        self, db: Session, student_user_id: uuid.UUID
    ) -> StudentExamProfile:
        profile = db.get(StudentExamProfile, student_user_id)
        if profile is not None:
            return profile
        profile = StudentExamProfile(
            user_id=student_user_id,
            major_category_code="academic_master",
            major_code="cs_academic",
            subject_codes=[],
        )
        db.add(profile)
        db.flush()
        return profile
