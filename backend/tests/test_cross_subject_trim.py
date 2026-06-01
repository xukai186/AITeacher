from datetime import date, timedelta

from sqlalchemy import select

from app.auth.security import hash_password
from app.models import DailyTask, MasterPlan, MasterPlanVersion, Package, StudentProfile, StudentSubject, UserRole
from app.services.master_planner import MasterPlannerService, subject_weights_for_student
from app.services.planning import PlanningService
from tests.factories import make_org, make_user


def test_subject_weights_from_package_order(db_session):
    org = make_org(db_session)
    pkg = Package(org_id=org.id, name="全科", subject_codes=["english", "math"])
    db_session.add(pkg)
    db_session.flush()

    student = make_user(
        db_session,
        org,
        role=UserRole.student,
        email="cross@demo.example",
        password_hash=hash_password("pw"),
    )
    db_session.add(StudentProfile(user_id=student.id, exam_year=2027, package_id=pkg.id))
    db_session.add(StudentSubject(student_user_id=student.id, subject_code="english"))
    db_session.add(StudentSubject(student_user_id=student.id, subject_code="math"))
    db_session.commit()

    weights = subject_weights_for_student(db_session, student.id)
    assert weights["english"] > weights["math"]


def test_cross_subject_trim_protects_high_weight_subject(db_session):
    org = make_org(db_session)
    pkg = Package(org_id=org.id, name="全科", subject_codes=["english", "math"])
    db_session.add(pkg)
    db_session.flush()

    student = make_user(
        db_session,
        org,
        role=UserRole.student,
        email="cross2@demo.example",
        password_hash=hash_password("pw"),
    )
    db_session.add(StudentProfile(user_id=student.id, exam_year=2027, package_id=pkg.id))
    db_session.add(StudentSubject(student_user_id=student.id, subject_code="english"))
    db_session.add(StudentSubject(student_user_id=student.id, subject_code="math"))
    db_session.commit()
    PlanningService().create_initial_plans(db_session, student_user_id=student.id)
    db_session.commit()

    tomorrow = date.today() + timedelta(days=1)
    plan = db_session.execute(
        select(MasterPlan).where(MasterPlan.student_user_id == student.id)
    ).scalar_one()
    version = db_session.get(MasterPlanVersion, plan.current_version_id)
    version.daily_time_budget_json = [{"date": tomorrow.isoformat(), "minutes": 70}]
    db_session.flush()

    # math (lower package weight): study 50
    db_session.add(
        DailyTask(
            student_user_id=student.id,
            date=tomorrow,
            subject_code="math",
            type="study",
            ref_id=None,
            status="pending",
            est_minutes=50,
            title="数学刷题",
        )
    )
    # english (higher weight): study 50 — should survive over math study
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
    assert trim.scheduled_minutes_after <= 70
    assert trim.cancelled_by_subject.get("math", 0) >= 1

    tasks = {
        (t.subject_code, t.type): t.status
        for t in db_session.execute(
            select(DailyTask).where(
                DailyTask.student_user_id == student.id,
                DailyTask.date == tomorrow,
                DailyTask.type == "study",
            )
        ).scalars()
    }
    assert tasks[("english", "study")] == "pending"
    assert tasks[("math", "study")] == "cancelled"
