from datetime import date, timedelta

from app.auth.security import hash_password
from app.models import StudentProfile, StudentSubject, UserRole
from app.services.agent_tools import default_tool_registry
from app.services.planning import PlanningService
from tests.factories import make_org, make_user


def test_agent_tool_registry_generate_daily_tasks(db_session):
    org = make_org(db_session)
    student = make_user(
        db_session,
        org,
        role=UserRole.student,
        email="tools@demo.example",
        password_hash=hash_password("pw"),
    )
    db_session.add(StudentProfile(user_id=student.id, exam_year=2027))
    db_session.add(StudentSubject(student_user_id=student.id, subject_code="english"))
    db_session.commit()
    PlanningService().create_initial_plans(db_session, student_user_id=student.id)
    db_session.commit()

    ctx = default_tool_registry.call(
        db_session,
        "get_subject_context",
        student_user_id=student.id,
        subject_code="english",
    )
    assert ctx.subject_code == "english"

    tomorrow = date.today() + timedelta(days=1)
    out = default_tool_registry.call(
        db_session,
        "generate_daily_tasks",
        student_user_id=student.id,
        subject_code="english",
        target_date=tomorrow,
    )
    assert out.target_date == tomorrow
    assert "generate_daily_tasks" in default_tool_registry.names()
