from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.permissions import assert_can_access_student, require_admin
from app.database import get_db
from app.models import ExamMajor, StudentExamProfile, User
from app.schemas.exam_profile import ExamProfileIn, ExamProfileOut
from app.services.audit import record_audit
from app.services.exam_profile import ExamProfileService, KNOWN_SUBJECT_CODES
from app.services.placement import PlacementService
from app.services.planning import PlanningService

router = APIRouter(prefix="/admin/students", tags=["admin-exam-profile"])


def _resolve_major(db: Session, payload: ExamProfileIn) -> ExamMajor:
    major = db.get(ExamMajor, payload.major_code)
    if major is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "major_code not found")
    if major.category_code != payload.major_category_code:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "major_code does not belong to major_category_code"
        )
    return major


def _normalize_subject_codes(payload: ExamProfileIn, major: ExamMajor) -> list[str]:
    if payload.subject_codes is None:
        return list(major.default_subject_codes)
    deduped = list(dict.fromkeys(payload.subject_codes))
    unknown = sorted(set(deduped) - set(KNOWN_SUBJECT_CODES))
    if unknown:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"unknown subject codes: {', '.join(unknown)}",
        )
    return deduped


def _to_out(profile: StudentExamProfile, major: ExamMajor) -> ExamProfileOut:
    return ExamProfileOut(
        major_category_code=profile.major_category_code,
        major_code=profile.major_code,
        major_name=major.name,
        english_track=profile.english_track,
        math_track=profile.math_track,
        effective_english_track=profile.english_track or major.default_english_track,
        effective_math_track=profile.math_track or major.default_math_track,
        subject_codes=list(profile.subject_codes),
        cet_status=profile.cet_status,
        cet_score=profile.cet_score,
        math_mastery_level=profile.math_mastery_level,
        profile_completed_at=profile.profile_completed_at,
        is_complete=profile.profile_completed_at is not None and bool(profile.major_code),
    )


def _load_profile_or_404(db: Session, student_id: uuid.UUID) -> tuple[StudentExamProfile, ExamMajor]:
    row = db.execute(
        select(StudentExamProfile, ExamMajor)
        .join(ExamMajor, StudentExamProfile.major_code == ExamMajor.code)
        .where(StudentExamProfile.user_id == student_id)
    ).one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "exam profile not found")
    profile, major = row
    return profile, major


@router.get("/{student_id}/exam-profile", response_model=ExamProfileOut)
def get_exam_profile(
    student_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin()),
) -> ExamProfileOut:
    assert_can_access_student(db, admin, student_id)
    profile, major = _load_profile_or_404(db, student_id)
    return _to_out(profile, major)


@router.put("/{student_id}/exam-profile", response_model=ExamProfileOut)
def put_exam_profile(
    student_id: uuid.UUID,
    payload: ExamProfileIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin()),
) -> ExamProfileOut:
    assert_can_access_student(db, admin, student_id)
    profile_service = ExamProfileService()
    old_effective = profile_service.get_effective(db, student_id)
    major = _resolve_major(db, payload)
    subject_codes = _normalize_subject_codes(payload, major)

    profile = db.get(StudentExamProfile, student_id)
    if profile is None:
        profile = StudentExamProfile(
            user_id=student_id,
            major_category_code=payload.major_category_code,
            major_code=payload.major_code,
            subject_codes=subject_codes,
        )
        db.add(profile)

    profile.major_category_code = payload.major_category_code
    profile.major_code = payload.major_code
    profile.english_track = payload.english_track
    profile.math_track = payload.math_track
    profile.subject_codes = subject_codes
    profile.cet_status = payload.cet_status
    profile.cet_score = payload.cet_score
    profile.math_mastery_level = payload.math_mastery_level
    db.flush()
    new_effective = profile_service.get_effective(db, student_id)
    if profile.profile_completed_at is not None:
        profile_service.sync_student_subjects(db, student_id, subject_codes)
    if old_effective is not None and new_effective is not None:
        profile_service.invalidate_placement_on_track_change(
            db,
            student_user_id=student_id,
            old_effective=old_effective,
            new_effective=new_effective,
        )

    change_kind = ExamProfileService.profile_change_kind(old_effective, new_effective)
    if profile.profile_completed_at is not None and change_kind == "baseline":
        PlanningService().light_revise_from_profile(db, student_id)
        record_audit(
            db,
            actor=admin,
            action="student.exam_profile.light_revise",
            target_type="student",
            target_id=str(student_id),
            before={
                "cet_status": old_effective.cet_status if old_effective else None,
                "cet_score": old_effective.cet_score if old_effective else None,
                "math_mastery_level": (
                    old_effective.math_mastery_level if old_effective else None
                ),
            },
            after={
                "cet_status": new_effective.cet_status if new_effective else None,
                "cet_score": new_effective.cet_score if new_effective else None,
                "math_mastery_level": (
                    new_effective.math_mastery_level if new_effective else None
                ),
            },
        )

    record_audit(
        db,
        actor=admin,
        action="student.exam_profile.upsert",
        target_type="student",
        target_id=str(student_id),
        after={
            "major_category_code": profile.major_category_code,
            "major_code": profile.major_code,
            "subject_codes": profile.subject_codes,
        },
    )
    db.commit()
    db.refresh(profile)
    return _to_out(profile, major)


@router.post("/{student_id}/exam-profile/confirm", response_model=ExamProfileOut)
def confirm_exam_profile(
    student_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin()),
) -> ExamProfileOut:
    assert_can_access_student(db, admin, student_id)
    profile = db.get(StudentExamProfile, student_id)
    if profile is None or not profile.major_code:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "exam profile with major is required")

    major = db.get(ExamMajor, profile.major_code)
    if major is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "major_code not found")

    subject_codes = list(profile.subject_codes) if profile.subject_codes else list(major.default_subject_codes)
    profile.subject_codes = subject_codes

    ExamProfileService().sync_student_subjects(db, student_id, subject_codes)
    if profile.profile_completed_at is None:
        profile.profile_completed_at = datetime.now(timezone.utc)

    for code in subject_codes:
        try:
            PlacementService.start(db, student_id, subject_code=code)
        except HTTPException:
            # Confirm should stay idempotent even when placement papers/jobs already exist.
            pass

    record_audit(
        db,
        actor=admin,
        action="student.exam_profile.confirm",
        target_type="student",
        target_id=str(student_id),
        after={"major_code": profile.major_code, "subject_codes": subject_codes},
    )
    db.commit()
    db.refresh(profile)
    return _to_out(profile, major)
