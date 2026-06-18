from sqlalchemy import select

from app.auth.security import hash_password
from app.models import StudentProfile, StudentSubject, UserRole
from app.services.self_test import SelfTestService
from tests.factories import make_org, make_user
from tests.paper_gen_job_helpers import finish_paper_gen_jobs, start_placement_and_wait


def _seed_student(db):
    org = make_org(db)
    student = make_user(
        db,
        org,
        role=UserRole.student,
        email="papers@demo.example",
        password_hash=hash_password("pw"),
    )
    db.add(StudentProfile(user_id=student.id, exam_year=2027))
    db.add(StudentSubject(student_user_id=student.id, subject_code="english"))
    db.commit()
    return student


def _token(client):
    return client.post(
        "/auth/login", json={"email": "papers@demo.example", "password": "pw"}
    ).json()["access_token"]


def test_list_student_papers_merges_placement_and_self_test(client, db_session):
    student = _seed_student(db_session)
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}

    start_placement_and_wait(client, token, db_session=db_session)
    paper, _ = SelfTestService.generate(db_session, student.id, "english")
    finish_paper_gen_jobs(db_session)
    db_session.commit()

    resp = client.get("/student/papers", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    types = {row["paper_type"] for row in body}
    assert types == {"placement", "self_test"}

    filtered = client.get(
        "/student/papers",
        headers=headers,
        params={"paper_type": "self_test", "status": "ready"},
    )
    assert filtered.status_code == 200
    assert len(filtered.json()) == 1
    assert filtered.json()[0]["paper_type"] == "self_test"
