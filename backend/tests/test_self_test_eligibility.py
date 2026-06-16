from datetime import date, datetime, timedelta, timezone

from app.auth.security import hash_password
from app.models import SelfTestGrade, SelfTestPaper, SelfTestSubmission, StudentProfile, StudentSubject, UserRole
from app.services.self_test import SelfTestService
from app.services.self_test_eligibility import SelfTestEligibilityService
from tests.factories import make_org, make_user
from tests.paper_gen_job_helpers import finish_paper_gen_jobs


def _student(db):
    org = make_org(db)
    student = make_user(
        db,
        org,
        role=UserRole.student,
        email="elig@demo.example",
        password_hash=hash_password("pw"),
    )
    db.add(StudentProfile(user_id=student.id, exam_year=2027))
    db.add(StudentSubject(student_user_id=student.id, subject_code="english"))
    db.commit()
    return student


def test_first_self_test_is_eligible(db_session):
    student = _student(db_session)
    result = SelfTestEligibilityService().check(
        db_session, student_user_id=student.id, subject_code="english"
    )
    assert result.allowed is True


def test_blocks_when_ready_paper_in_progress(db_session):
    student = _student(db_session)
    paper, _ = SelfTestService.generate(db_session, student.id, "english")
    finish_paper_gen_jobs(db_session)
    db_session.commit()
    result = SelfTestEligibilityService().check(
        db_session, student_user_id=student.id, subject_code="english"
    )
    assert result.allowed is False
    assert any("未提交" in r for r in result.reasons)


def test_blocks_within_five_days_of_last_graded(db_session):
    student = _student(db_session)
    paper, _ = SelfTestService.generate(db_session, student.id, "english")
    finish_paper_gen_jobs(db_session)
    db_session.commit()
    now = datetime.now(timezone.utc)
    sub = SelfTestSubmission(
        paper_id=paper.id,
        student_user_id=student.id,
        status="submitted",
        submitted_at=now,
    )
    db_session.add(sub)
    db_session.flush()
    db_session.add(SelfTestGrade(submission_id=sub.id, total_score=5, detail_json={}))
    db_session.commit()

    result = SelfTestEligibilityService().check(
        db_session, student_user_id=student.id, subject_code="english"
    )
    assert result.allowed is False
    assert any("间隔" in r for r in result.reasons)


def test_allows_after_five_days(db_session):
    student = _student(db_session)
    paper, _ = SelfTestService.generate(db_session, student.id, "english")
    finish_paper_gen_jobs(db_session)
    db_session.commit()
    sub = SelfTestSubmission(
        paper_id=paper.id,
        student_user_id=student.id,
        status="submitted",
        submitted_at=datetime.now(timezone.utc),
    )
    db_session.add(sub)
    db_session.flush()
    db_session.add(SelfTestGrade(submission_id=sub.id, total_score=5, detail_json={}))
    db_session.commit()

    as_of = date.today() + timedelta(days=5)
    result = SelfTestEligibilityService().check(
        db_session,
        student_user_id=student.id,
        subject_code="english",
        as_of=as_of,
    )
    assert result.allowed is True
