from datetime import date

from app.auth.security import hash_password
from app.models import DailyTask, StudentProfile, StudentSubject, UserRole
from app.services.tasks import TaskGenerator
from tests.factories import make_org, make_user


def _student_token(client, db_session):
    org = make_org(db_session)
    student = make_user(
        db_session,
        org,
        role=UserRole.student,
        email="today-tasks@demo.example",
        password_hash=hash_password("pw"),
    )
    db_session.add(StudentProfile(user_id=student.id, exam_year=2027))
    db_session.commit()
    token = client.post("/auth/login", json={"email": "today-tasks@demo.example", "password": "pw"}).json()[
        "access_token"
    ]
    return student, token


def test_generate_7_days_tasks(db_session):
    org = make_org(db_session)
    student = make_user(
        db_session,
        org,
        role=UserRole.student,
        email="s@demo.example",
        password_hash=hash_password("pw"),
    )
    db_session.add(StudentProfile(user_id=student.id, exam_year=2027))
    db_session.add(StudentSubject(student_user_id=student.id, subject_code="english"))
    db_session.commit()

    gen = TaskGenerator()
    gen.generate_next_7_days(db_session, student_user_id=student.id, today=date.today())
    assert db_session.query(DailyTask).count() == 7

    gen.generate_next_7_days(db_session, student_user_id=student.id, today=date.today())
    assert db_session.query(DailyTask).count() == 7


def test_generate_7_days_tasks_all_subjects(db_session):
    org = make_org(db_session)
    student = make_user(
        db_session,
        org,
        role=UserRole.student,
        email="s2@demo.example",
        password_hash=hash_password("pw"),
    )
    db_session.add(StudentProfile(user_id=student.id, exam_year=2027))
    for code in ("english", "math", "politics"):
        db_session.add(StudentSubject(student_user_id=student.id, subject_code=code))
    db_session.commit()

    TaskGenerator().generate_next_7_days(db_session, student_user_id=student.id, today=date.today())
    assert db_session.query(DailyTask).count() == 21


def test_today_tasks_includes_payload_json(client, db_session):
    student, token = _student_token(client, db_session)
    today = date.today()
    db_session.add(
        DailyTask(
            student_user_id=student.id,
            date=today,
            subject_code="english",
            type="study",
            status="pending",
            est_minutes=30,
            title="Weekly focus",
            payload_json={"source": "weekly_goal", "syllabus_node_id": "node-1"},
        )
    )
    db_session.commit()

    resp = client.get("/student/tasks/today", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["date"] == today.isoformat()
    assert len(body["tasks"]) == 1
    assert body["tasks"][0]["payload_json"] == {
        "source": "weekly_goal",
        "syllabus_node_id": "node-1",
    }

