from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import ExamMajor, PlacementPaper, PlacementQuestion, PlacementSubmission, StudentExamProfile, StudentSubject
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

    def invalidate_placement_on_track_change(
        self,
        db: Session,
        student_user_id: uuid.UUID,
        old_effective: EffectiveExamProfile,
        new_effective: EffectiveExamProfile,
    ) -> None:
        old_subjects = set(old_effective.subject_codes)
        new_subjects = set(new_effective.subject_codes)
        tracks_changed = (
            old_effective.english_track != new_effective.english_track
            or old_effective.math_track != new_effective.math_track
        )
        subjects_changed = old_subjects != new_subjects
        if not tracks_changed and not subjects_changed:
            return
        from app.services.paper_gen_jobs import PaperGenJobService, kick_paper_gen_job

        papers = list(
            db.execute(
                select(PlacementPaper).where(
                    PlacementPaper.student_user_id == student_user_id
                )
            )
            .scalars()
            .all()
        )
        paper_by_subject = {paper.subject_code: paper for paper in papers}
        for subject_code in new_subjects:
            if subject_code in paper_by_subject:
                continue
            paper = PlacementPaper(
                student_user_id=student_user_id,
                subject_code=subject_code,
                status="generating",
            )
            db.add(paper)
            db.flush()
            papers.append(paper)

        job_service = PaperGenJobService()
        for paper in papers:
            submitted = db.execute(
                select(PlacementSubmission.id).where(
                    PlacementSubmission.paper_id == paper.id,
                    PlacementSubmission.student_user_id == student_user_id,
                )
            ).scalar_one_or_none()
            if submitted is not None:
                continue

            db.execute(delete(PlacementQuestion).where(PlacementQuestion.paper_id == paper.id))
            paper.status = "generating"

            if paper.subject_code not in new_subjects:
                continue

            enqueued = job_service.enqueue(
                db,
                student_user_id=student_user_id,
                subject_code=paper.subject_code,
                purpose="placement",
                paper_id=paper.id,
            )
            kick_paper_gen_job(enqueued.job_id)
