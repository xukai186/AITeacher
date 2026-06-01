from datetime import date, timedelta

from sqlalchemy import select

from app.auth.security import hash_password
from app.models import PlanReviewJob, StudentProfile, StudentSubject, UserRole
from app.services.daily_task_generation import DailyTaskGenerationService
from app.services.plan_review_jobs import PlanReviewJobRunner
from app.services.planning import PlanningService
from tests.factories import make_org, make_user


def test_daily_generation_runs_plan_review_for_enabled_subjects(db_session):
    org = make_org(db_session)
    student = make_user(
        db_session,
        org,
        role=UserRole.student,
        email="daily-gen@demo.example",
        password_hash=hash_password("pw"),
    )
    db_session.add(StudentProfile(user_id=student.id, exam_year=2027))
    db_session.add(StudentSubject(student_user_id=student.id, subject_code="english"))
    db_session.commit()
    PlanningService().create_initial_plans(db_session, student_user_id=student.id)
    db_session.commit()

    tomorrow = date.today() + timedelta(days=1)
    result = DailyTaskGenerationService().run(db_session, target_date=tomorrow)
    assert result.subjects_processed == 1
    assert result.subjects_failed == 0
    assert result.target_date == tomorrow

    jobs = db_session.execute(select(PlanReviewJob)).scalars().all()
    assert len(jobs) >= 1

    PlanReviewJobRunner().run_pending(db_session, limit=10)
    db_session.commit()

    assert any(j.status == "succeeded" for j in jobs)
