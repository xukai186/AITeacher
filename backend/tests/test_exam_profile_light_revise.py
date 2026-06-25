from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app.models import (
    MasterPlan,
    MasterPlanVersion,
    StudentExamProfile,
    SubjectPlan,
    SubjectPlanVersion,
    UserRole,
)
from app.seed_exam_majors import seed_exam_majors
from app.services.exam_profile import ExamProfileService
from app.services.planning import PlanningService
from tests.factories import make_org, make_user


def _seed_student_with_confirmed_profile(db_session):
    seed_exam_majors(db_session)
    org = make_org(db_session)
    student = make_user(
        db_session,
        org,
        role=UserRole.student,
        email="light-revise@demo.example",
    )
    ExamProfileService().sync_student_subjects(
        db_session, student.id, ["english", "math", "politics"]
    )
    db_session.add(
        StudentExamProfile(
            user_id=student.id,
            major_category_code="academic_master",
            major_code="cs_academic",
            subject_codes=["english", "math", "politics"],
            cet_status="cet4",
            profile_completed_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()
    PlanningService().create_initial_plans(db_session, student.id)
    db_session.commit()
    return student


def test_light_revise_bumps_english_subject_version_only(db_session):
    student = _seed_student_with_confirmed_profile(db_session)

    politics_plan = db_session.execute(
        select(SubjectPlan).where(
            SubjectPlan.student_user_id == student.id,
            SubjectPlan.subject_code == "politics",
        )
    ).scalar_one()
    politics_before = db_session.get(SubjectPlanVersion, politics_plan.current_version_id)
    politics_version_before = politics_before.version

    english_plan = db_session.execute(
        select(SubjectPlan).where(
            SubjectPlan.student_user_id == student.id,
            SubjectPlan.subject_code == "english",
        )
    ).scalar_one()
    english_before = db_session.get(SubjectPlanVersion, english_plan.current_version_id)
    english_version_before = english_before.version

    profile = db_session.get(StudentExamProfile, student.id)
    profile.cet_status = "not_taken"
    db_session.flush()

    PlanningService().light_revise_from_profile(db_session, student.id)
    db_session.commit()

    politics_plan = db_session.execute(
        select(SubjectPlan).where(
            SubjectPlan.student_user_id == student.id,
            SubjectPlan.subject_code == "politics",
        )
    ).scalar_one()
    politics_after = db_session.get(SubjectPlanVersion, politics_plan.current_version_id)
    assert politics_after.version == politics_version_before

    english_plan = db_session.execute(
        select(SubjectPlan).where(
            SubjectPlan.student_user_id == student.id,
            SubjectPlan.subject_code == "english",
        )
    ).scalar_one()
    english_after = db_session.get(SubjectPlanVersion, english_plan.current_version_id)
    assert english_after.version == english_version_before + 1
    assert "CET" in english_after.phases_json[0]["notes"]


def test_light_revise_small_budget_auto_activates(db_session):
    student = _seed_student_with_confirmed_profile(db_session)
    master = db_session.execute(
        select(MasterPlan).where(MasterPlan.student_user_id == student.id)
    ).scalar_one()

    profile = db_session.get(StudentExamProfile, student.id)
    profile.cet_status = "not_taken"
    db_session.flush()

    result = PlanningService().light_revise_from_profile(db_session, student.id)
    db_session.commit()

    assert result is not None
    assert result.auto_activated is True
    assert result.pending is False
    db_session.refresh(master)
    assert master.pending_version_id is None


def test_light_revise_large_budget_sets_pending(db_session):
    student = _seed_student_with_confirmed_profile(db_session)
    master = db_session.execute(
        select(MasterPlan).where(MasterPlan.student_user_id == student.id)
    ).scalar_one()
    current = db_session.get(MasterPlanVersion, master.current_version_id)
    low_budget = [
        {"date": (date.today() + timedelta(days=i)).isoformat(), "minutes": 60}
        for i in range(7)
    ]
    current.daily_time_budget_json = low_budget
    db_session.flush()

    profile = db_session.get(StudentExamProfile, student.id)
    profile.cet_status = "not_taken"
    profile.math_mastery_level = "zero"
    db_session.flush()

    result = PlanningService().light_revise_from_profile(db_session, student.id)
    db_session.commit()

    assert result is not None
    assert result.pending is True
    db_session.refresh(master)
    assert master.pending_version_id is not None
