from datetime import date, timedelta

from sqlalchemy import select

from app.auth.security import hash_password
from app.models import DailyTask, MasterPlan, MasterPlanVersion, StudentProfile, StudentSubject, UserRole
from app.services.master_planner import MasterPlannerService
from app.services.planning import PlanningService
from app.services.plan_review import PlanReviewService
from app.services.tasks import TaskGenerator
from tests.factories import make_org, make_user


def _seed_student(db):
    org = make_org(db)
    student = make_user(
        db,
        org,
        role=UserRole.student,
        email="plan-review@demo.example",
        password_hash=hash_password("pw"),
    )
    db.add(StudentProfile(user_id=student.id, exam_year=2027))
    db.add(StudentSubject(student_user_id=student.id, subject_code="english"))
    db.commit()
    PlanningService().create_initial_plans(db, student_user_id=student.id)
    db.commit()
    return student


def _token(client):
    return client.post(
        "/auth/login",
        json={"email": "plan-review@demo.example", "password": "pw"},
    ).json()["access_token"]


def test_self_test_submit_triggers_plan_review_tasks(client, db_session):
    student = _seed_student(db_session)
    token = _token(client)

    start = client.post("/student/placement/start", headers={"Authorization": f"Bearer {token}"})
    assert start.status_code == 200
    paper_id = client.get("/student/placement", headers={"Authorization": f"Bearer {token}"}).json()[0]["id"]
    paper = client.get(f"/student/placement/{paper_id}", headers={"Authorization": f"Bearer {token}"}).json()
    assert (
        client.post(
            f"/student/placement/{paper_id}/submit",
            json={"answers": [{"question_id": q["id"], "content": "Z"} for q in paper["questions"]]},
            headers={"Authorization": f"Bearer {token}"},
        ).status_code
        == 200
    )

    gen = client.post(
        "/student/self-tests/generate",
        json={"subject_code": "english"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert gen.status_code == 200
    self_paper_id = gen.json()["id"]
    self_paper = client.get(
        f"/student/self-tests/{self_paper_id}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    assert (
        client.post(
            f"/student/self-tests/{self_paper_id}/submit",
            json={"answers": [{"question_id": q["id"], "content": "Z"} for q in self_paper["questions"]]},
            headers={"Authorization": f"Bearer {token}"},
        ).status_code
        == 200
    )

    tomorrow = date.today() + timedelta(days=1)
    tasks = db_session.execute(
        select(DailyTask).where(
            DailyTask.student_user_id == student.id,
            DailyTask.date == tomorrow,
            DailyTask.status == "pending",
        )
    ).scalars().all()
    types = {t.type for t in tasks}
    assert "review_wrong" in types


def test_master_planner_trims_low_priority_study_tasks(db_session):
    student = _seed_student(db_session)
    tomorrow = date.today() + timedelta(days=1)

    plan = db_session.execute(
        select(MasterPlan).where(MasterPlan.student_user_id == student.id)
    ).scalar_one()
    version = db_session.get(MasterPlanVersion, plan.current_version_id)
    version.daily_time_budget_json = [{"date": tomorrow.isoformat(), "minutes": 50}]
    db_session.flush()

    db_session.add(
        DailyTask(
            student_user_id=student.id,
            date=tomorrow,
            subject_code="english",
            type="study",
            ref_id=None,
            status="pending",
            est_minutes=40,
            title="刷题",
        )
    )
    db_session.add(
        DailyTask(
            student_user_id=student.id,
            date=tomorrow,
            subject_code="english",
            type="review_wrong",
            ref_id=None,
            status="pending",
            est_minutes=30,
            title="错题复习",
        )
    )
    db_session.commit()

    trim = MasterPlannerService().trim_tasks_by_budget(
        db_session, student_user_id=student.id, target_date=tomorrow
    )
    db_session.commit()

    assert trim.cancelled_count >= 1
    assert trim.scheduled_minutes_after <= 50

    tasks = db_session.execute(
        select(DailyTask).where(
            DailyTask.student_user_id == student.id,
            DailyTask.date == tomorrow,
        )
    ).scalars().all()
    review = next(t for t in tasks if t.type == "review_wrong")
    assert review.status == "pending"
    study = next(t for t in tasks if t.type == "study")
    assert study.status == "cancelled"


def test_plan_review_service_runs_tools(db_session):
    student = _seed_student(db_session)
    TaskGenerator().generate_next_7_days(db_session, student_user_id=student.id, today=date.today())

    tomorrow = date.today() + timedelta(days=1)
    result = PlanReviewService().run_subject_review(
        db_session,
        student_user_id=student.id,
        subject_code="english",
        trigger="test",
        target_date=tomorrow,
    )
    db_session.commit()
    assert result.trigger == "test"
    assert result.apply.created_count + result.apply.skipped_count >= 0
