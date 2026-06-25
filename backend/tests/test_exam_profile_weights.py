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


def test_trim_cancels_low_weight_subject_first(db_session):
    from datetime import date, timedelta

    from app.models import DailyTask, MasterPlan, MasterPlanVersion, StudentProfile
    from app.services.master_planner import MasterPlannerService
    from app.services.planning import PlanningService

    org = make_org(db_session)
    student = make_user(db_session, org, role=UserRole.student, email="trim@demo.example")
    add_complete_exam_profile(db_session, student.id, subject_codes=["english", "politics"])
    ExamProfileService().sync_student_subjects(db_session, student.id, ["english", "politics"])
    db_session.commit()
    prof = db_session.get(StudentExamProfile, student.id)
    prof.cet_status = "not_taken"
    prof.subject_codes = ["english", "politics"]
    db_session.add(StudentProfile(user_id=student.id, exam_year=2027))
    db_session.commit()

    PlanningService().create_initial_plans(db_session, student.id)
    db_session.commit()

    tomorrow = date.today() + timedelta(days=1)
    plan = db_session.query(MasterPlan).filter_by(student_user_id=student.id).one()
    version = db_session.get(MasterPlanVersion, plan.current_version_id)
    version.daily_time_budget_json = [{"date": tomorrow.isoformat(), "minutes": 70}]
    db_session.add(
        DailyTask(
            student_user_id=student.id,
            date=tomorrow,
            subject_code="politics",
            type="study",
            ref_id=None,
            status="pending",
            est_minutes=50,
            title="政治刷题",
        )
    )
    db_session.add(
        DailyTask(
            student_user_id=student.id,
            date=tomorrow,
            subject_code="english",
            type="study",
            ref_id=None,
            status="pending",
            est_minutes=50,
            title="英语刷题",
        )
    )
    db_session.commit()

    trim = MasterPlannerService().trim_tasks_by_budget(
        db_session, student_user_id=student.id, target_date=tomorrow
    )
    db_session.commit()

    assert trim.cancelled_count >= 1
    assert trim.cancelled_by_subject.get("politics", 0) >= 1


def test_apply_recommendations_adds_english_boost_for_cet_not_taken(db_session):
    from datetime import date, timedelta

    from app.services.subject_agent import SubjectAgentService

    org = make_org(db_session)
    student = make_user(db_session, org, role=UserRole.student, email="boost@demo.example")
    add_complete_exam_profile(db_session, student.id)
    _sync_default_subjects(db_session, student.id)
    prof = db_session.get(StudentExamProfile, student.id)
    prof.cet_status = "not_taken"
    db_session.commit()

    day = date.today() + timedelta(days=1)
    result = SubjectAgentService().apply_report_recommendations(
        db_session,
        student_user_id=student.id,
        subject_code="english",
        target_date=day,
    )
    assert any("基础" in t.title for t in result.created)

    result2 = SubjectAgentService().apply_report_recommendations(
        db_session,
        student_user_id=student.id,
        subject_code="english",
        target_date=day,
    )
    assert result2.skipped_count >= 1
