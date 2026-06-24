from datetime import datetime, timezone

from sqlalchemy import select

from app.models import StudentExamProfile, StudentSubject, UserRole
from app.seed_exam_majors import seed_exam_majors
from app.services.exam_profile import ExamProfileService
from tests.factories import make_org, make_user


def test_get_effective_merges_major_defaults(db_session):
    seed_exam_majors(db_session)
    org = make_org(db_session)
    student = make_user(db_session, org, role=UserRole.student, email="eff-merge@demo.example")

    db_session.add(
        StudentExamProfile(
            user_id=student.id,
            major_category_code="academic_master",
            major_code="cs_academic",
            english_track="english_2",
            math_track=None,
            subject_codes=["english", "math", "politics"],
        )
    )
    db_session.commit()

    eff = ExamProfileService().get_effective(db_session, student.id)
    assert eff is not None
    assert eff.english_track == "english_2"
    assert eff.math_track == "math_1"
    assert eff.major_name == "计算机科学与技术"


def test_get_effective_returns_none_without_profile(db_session):
    seed_exam_majors(db_session)
    org = make_org(db_session)
    student = make_user(db_session, org, role=UserRole.student, email="no-profile@demo.example")

    assert ExamProfileService().get_effective(db_session, student.id) is None


def test_sync_subjects_enables_and_disables(db_session):
    seed_exam_majors(db_session)
    org = make_org(db_session)
    student = make_user(db_session, org, role=UserRole.student, email="sync-subj@demo.example")

    for code in ("english", "math", "politics"):
        db_session.add(
            StudentSubject(student_user_id=student.id, subject_code=code, enabled=True)
        )
    db_session.commit()

    ExamProfileService().sync_student_subjects(
        db_session, student.id, ["english", "politics"]
    )
    db_session.commit()

    rows = {
        row.subject_code: row.enabled
        for row in db_session.execute(
            select(StudentSubject).where(StudentSubject.student_user_id == student.id)
        ).scalars()
    }
    assert rows == {"english": True, "math": False, "politics": True}


def test_is_profile_complete_requires_confirm(db_session):
    seed_exam_majors(db_session)
    org = make_org(db_session)
    student = make_user(db_session, org, role=UserRole.student, email="incomplete@demo.example")

    db_session.add(
        StudentExamProfile(
            user_id=student.id,
            major_category_code="academic_master",
            major_code="cs_academic",
            subject_codes=["english", "math", "politics"],
        )
    )
    db_session.commit()

    svc = ExamProfileService()
    assert svc.is_complete(db_session, student.id) is False

    profile = db_session.get(StudentExamProfile, student.id)
    profile.profile_completed_at = datetime.now(timezone.utc)
    db_session.commit()
    assert svc.is_complete(db_session, student.id) is True
