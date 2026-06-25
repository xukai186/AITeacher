from app.models import StudentExamProfile, UserRole
from app.services.exam_profile import ExamProfileService
from app.services.exam_profile_weights import ExamProfileWeightService
from tests.exam_profile_helpers import add_complete_exam_profile
from tests.factories import make_org, make_user


def _sync_default_subjects(db_session, student_id) -> None:
    ExamProfileService().sync_student_subjects(
        db_session, student_id, ["english", "math", "politics"]
    )
    db_session.flush()


def test_english_not_taken_has_higher_weight_than_cet6(db_session):
    org = make_org(db_session)
    student = make_user(db_session, org, role=UserRole.student, email="w1@demo.example")
    add_complete_exam_profile(db_session, student.id)
    _sync_default_subjects(db_session, student.id)
    prof = db_session.get(StudentExamProfile, student.id)
    prof.cet_status = "not_taken"
    db_session.flush()
    w = ExamProfileWeightService().subject_weights(db_session, student.id)
    assert w["english"] > w["politics"]

    prof.cet_status = "cet6"
    db_session.flush()
    w2 = ExamProfileWeightService().subject_weights(db_session, student.id)
    assert w2["english"] < w["english"]


def test_math_zero_has_higher_weight_than_strong(db_session):
    org = make_org(db_session)
    student = make_user(db_session, org, role=UserRole.student, email="w2@demo.example")
    add_complete_exam_profile(db_session, student.id)
    _sync_default_subjects(db_session, student.id)
    prof = db_session.get(StudentExamProfile, student.id)
    prof.math_mastery_level = "zero"
    db_session.flush()
    w = ExamProfileWeightService().subject_weights(db_session, student.id)
    prof.math_mastery_level = "strong"
    db_session.flush()
    w2 = ExamProfileWeightService().subject_weights(db_session, student.id)
    assert w["math"] > w2["math"]


def test_math_none_track_excludes_math_weight(db_session):
    org = make_org(db_session)
    student = make_user(db_session, org, role=UserRole.student, email="w3@demo.example")
    add_complete_exam_profile(db_session, student.id, subject_codes=["english", "politics"])
    ExamProfileService().sync_student_subjects(
        db_session, student.id, ["english", "politics"]
    )
    db_session.flush()
    prof = db_session.get(StudentExamProfile, student.id)
    prof.math_track = "none"
    prof.subject_codes = ["english", "politics"]
    db_session.flush()
    w = ExamProfileWeightService().subject_weights(db_session, student.id)
    assert "math" not in w
