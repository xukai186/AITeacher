from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.permissions import assert_can_access_student, require_roles
from app.database import get_db
from app.models import ExamMajor, StudentExamProfile, User, UserRole
from app.routers.admin_exam_profile import _load_profile_or_404, _normalize_subject_codes, _resolve_major, _to_out
from app.schemas.exam_profile import ExamProfileIn, ExamProfileOut
from app.services.audit import record_audit
from app.services.exam_profile import ExamProfileService
from app.services.placement import PlacementService
from app.services.planning import PlanningService

router = APIRouter(prefix="/staff/students", tags=["staff-exam-profile"])


@router.get("/{student_id}/exam-profile", response_model=ExamProfileOut)
def get_exam_profile(
    student_id: uuid.UUID,
    db: Session = Depends(get_db),
    staff: User = Depends(require_roles(UserRole.org_staff)),
) -> ExamProfileOut:
    assert_can_access_student(db, staff, student_id)
    profile, major = _load_profile_or_404(db, student_id)
    return _to_out(profile, major)


@router.put("/{student_id}/exam-profile", response_model=ExamProfileOut)
def put_exam_profile(
    student_id: uuid.UUID,
    payload: ExamProfileIn,
    db: Session = Depends(get_db),
    staff: User = Depends(require_roles(UserRole.org_staff)),
) -> ExamProfileOut:
    assert_can_access_student(db, staff, student_id)
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
            actor=staff,
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
        actor=staff,
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
    staff: User = Depends(require_roles(UserRole.org_staff)),
) -> ExamProfileOut:
    assert_can_access_student(db, staff, student_id)
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

    PlanningService().create_initial_plans(db, student_id)
    for code in subject_codes:
        try:
            PlacementService.start(db, student_id, subject_code=code)
        except HTTPException:
            # Confirm should stay idempotent even when placement papers/jobs already exist.
            pass

    record_audit(
        db,
        actor=staff,
        action="student.exam_profile.confirm",
        target_type="student",
        target_id=str(student_id),
        after={"major_code": profile.major_code, "subject_codes": subject_codes},
    )
    db.commit()
    db.refresh(profile)
    return _to_out(profile, major)
