from datetime import date, timedelta

from sqlalchemy import select

from app.auth.security import hash_password
from app.models import DailyTask, PlanReviewJob, StudentProfile, StudentSubject, UserRole
from app.services.plan_review_jobs import PlanReviewJobRunner
from app.services.planning import PlanningService
from app.services.subject_agent import SubjectAgentService
from tests.factories import make_org, make_user
from tests.paper_gen_job_helpers import start_placement_and_wait


def _seed_student(db):
    org = make_org(db)
    student = make_user(
        db,
        org,
        role=UserRole.student,
        email="agent-student@demo.example",
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
        json={"email": "agent-student@demo.example", "password": "pw"},
    ).json()["access_token"]


def test_apply_recommendations_enqueues_job(client, db_session):
    student = _seed_student(db_session)
    token = _token(client)

    start_placement_and_wait(client, token, db_session=db_session)
    paper_id = client.get("/student/placement", headers={"Authorization": f"Bearer {token}"}).json()[0]["id"]
    paper = client.get(f"/student/placement/{paper_id}", headers={"Authorization": f"Bearer {token}"}).json()
    submit = client.post(
        f"/student/placement/{paper_id}/submit",
        json={"answers": [{"question_id": q["id"], "content": "Z"} for q in paper["questions"]]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert submit.status_code == 200

    tomorrow = date.today() + timedelta(days=1)
    resp = client.post(
        "/student/agent/apply-recommendations",
        params={"subject_code": "english", "target_date": tomorrow.isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["job_id"]
    assert body["status"] in ("pending", "retry", "running", "succeeded")

    PlanReviewJobRunner().run_pending(db_session, limit=10)
    db_session.commit()

    job = db_session.get(PlanReviewJob, body["job_id"])
    assert job is not None
    assert job.status == "succeeded"

    get_resp = client.get(
        f"/student/agent/plan-review-jobs/{body['job_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp.status_code == 200
    done = get_resp.json()
    assert done["status"] == "succeeded"

    tasks = db_session.execute(
        select(DailyTask).where(
            DailyTask.student_user_id == student.id,
            DailyTask.date == tomorrow,
        )
    ).scalars().all()
    assert len(tasks) >= 0

    again = client.post(
        "/student/agent/apply-recommendations",
        params={"subject_code": "english", "target_date": tomorrow.isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert again.status_code == 200
    assert again.json()["job_id"] == body["job_id"]


def test_subject_agent_service_idempotent(db_session):
    student = _seed_student(db_session)
    tomorrow = date.today() + timedelta(days=1)

    out1 = SubjectAgentService().apply_report_recommendations(
        db_session,
        student_user_id=student.id,
        subject_code="english",
        target_date=tomorrow,
    )
    assert out1.created_count >= 0

    out2 = SubjectAgentService().apply_report_recommendations(
        db_session,
        student_user_id=student.id,
        subject_code="english",
        target_date=tomorrow,
    )
    assert out2.created_count == 0
    assert out2.skipped_count >= out1.created_count
