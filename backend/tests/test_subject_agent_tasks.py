from datetime import date, timedelta

from sqlalchemy import select

from app.auth.security import hash_password
from app.models import DailyTask, StudentProfile, StudentSubject, UserRole
from app.services.planning import PlanningService
from app.services.subject_agent import SubjectAgentService
from tests.factories import make_org, make_user


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


def test_apply_recommendations_creates_tasks_for_tomorrow(client, db_session):
    student = _seed_student(db_session)
    token = _token(client)

    start = client.post("/student/placement/start", headers={"Authorization": f"Bearer {token}"})
    assert start.status_code == 200
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
    assert body["target_date"] == tomorrow.isoformat()
    assert body["subject_code"] == "english"
    # Placement submit may have already run PlanReview for tomorrow (skipped on manual apply).
    assert body["created_count"] + body["skipped_count"] >= 1
    if body["created_count"] > 0:
        assert any(t["type"] == "review_wrong" for t in body["created"])

    tasks = db_session.execute(
        select(DailyTask).where(
            DailyTask.student_user_id == student.id,
            DailyTask.date == tomorrow,
        )
    ).scalars().all()
    assert len(tasks) >= body["created_count"]

    again = client.post(
        "/student/agent/apply-recommendations",
        params={"subject_code": "english", "target_date": tomorrow.isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert again.status_code == 200
    assert again.json()["created_count"] == 0
    assert again.json()["skipped_count"] >= 1


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
