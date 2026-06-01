from datetime import date, timedelta

from sqlalchemy import select

from app.auth.security import hash_password
from app.models import DailyTask, MasterPlan, MasterPlanVersion, StudentProfile, StudentSubject, UserRole
from app.services.master_plan_activation import MasterPlanActivationService
from app.services.planning import PlanningService
from tests.factories import make_org, make_user


def _student_with_plan(db):
    org = make_org(db)
    student = make_user(
        db,
        org,
        role=UserRole.student,
        email="master-plan@demo.example",
        password_hash=hash_password("pw"),
    )
    db.add(StudentProfile(user_id=student.id, exam_year=2027))
    db.add(StudentSubject(student_user_id=student.id, subject_code="english"))
    db.commit()
    PlanningService().create_initial_plans(db, student_user_id=student.id)
    db.commit()
    return student


def test_large_budget_change_creates_pending(db_session):
    student = _student_with_plan(db_session)
    plan = db_session.execute(
        select(MasterPlan).where(MasterPlan.student_user_id == student.id)
    ).scalar_one()
    current = db_session.get(MasterPlanVersion, plan.current_version_id)
    assert current is not None

    svc = MasterPlanActivationService()
    big_budget = [
        {"date": entry["date"], "minutes": 300}
        for entry in (current.daily_time_budget_json or [])
    ]
    result = svc.propose_version(
        db_session,
        plan=plan,
        daily_time_budget_json=big_budget,
        weekly_goals_json=current.weekly_goals_json,
        source="ai",
    )
    db_session.commit()

    assert result.pending is True
    assert result.change_ratio > 0.15
    db_session.refresh(plan)
    assert plan.pending_version_id is not None
    assert plan.current_version_id != plan.pending_version_id


def test_student_confirm_and_reject_pending(client, db_session):
    student = _student_with_plan(db_session)
    plan = db_session.execute(
        select(MasterPlan).where(MasterPlan.student_user_id == student.id)
    ).scalar_one()
    current = db_session.get(MasterPlanVersion, plan.current_version_id)
    svc = MasterPlanActivationService()
    new_budget = [
        {"date": entry["date"], "minutes": 60}
        for entry in (current.daily_time_budget_json or [])
    ]
    svc.propose_version(
        db_session,
        plan=plan,
        daily_time_budget_json=new_budget,
        weekly_goals_json=current.weekly_goals_json,
        source="ai",
    )
    db_session.commit()

    token = client.post(
        "/auth/login",
        json={"email": "master-plan@demo.example", "password": "pw"},
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    state = client.get("/student/master-plan", headers=headers)
    assert state.status_code == 200
    body = state.json()
    assert body["requires_confirmation"] is True
    assert body["pending_version"] is not None

    confirm = client.post("/student/master-plan/confirm", headers=headers)
    assert confirm.status_code == 200
    db_session.refresh(plan)
    assert plan.pending_version_id is None

    # create another pending for reject test
    current2 = db_session.get(MasterPlanVersion, plan.current_version_id)
    bigger = [
        {"date": entry["date"], "minutes": 240}
        for entry in (current2.daily_time_budget_json or [])
    ]
    svc.propose_version(
        db_session,
        plan=plan,
        daily_time_budget_json=bigger,
        weekly_goals_json=current2.weekly_goals_json,
        source="ai",
    )
    db_session.commit()

    reject = client.post("/student/master-plan/reject", headers=headers)
    assert reject.status_code == 204
    db_session.refresh(plan)
    assert plan.pending_version_id is None


def test_trim_may_propose_pending_master_plan(db_session):
    student = _student_with_plan(db_session)
    tomorrow = date.today() + timedelta(days=1)
    plan = db_session.execute(
        select(MasterPlan).where(MasterPlan.student_user_id == student.id)
    ).scalar_one()
    version = db_session.get(MasterPlanVersion, plan.current_version_id)
    version.daily_time_budget_json = [{"date": tomorrow.isoformat(), "minutes": 200}]
    for i in range(8):
        db_session.add(
            DailyTask(
                student_user_id=student.id,
                date=tomorrow,
                subject_code="english",
                type="study",
                status="pending",
                est_minutes=40,
                title=f"t{i}",
            )
        )
    db_session.commit()

    from app.services.master_planner import MasterPlannerService

    trim = MasterPlannerService().trim_tasks_by_budget(
        db_session, student_user_id=student.id, target_date=tomorrow
    )
    assert trim.cancelled_count > 0

    svc = MasterPlanActivationService()
    svc.propose_daily_budget(
        db_session,
        student_user_id=student.id,
        target_date=tomorrow,
        new_minutes_for_day=trim.scheduled_minutes_after,
        source="ai",
    )
    db_session.commit()
    db_session.refresh(plan)
    # Large cut from 200 to ~scheduled_after may require confirmation
    if trim.scheduled_minutes_after < 170:
        assert plan.pending_version_id is not None
