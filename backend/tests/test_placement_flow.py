from sqlalchemy import select

from app.auth.security import hash_password
from app.models import PlacementPaper, StudentProfile, StudentSubject, UserRole
from tests.factories import make_org, make_user


def _seed_student(db):
    org = make_org(db)
    student = make_user(db, org, role=UserRole.student, email="student@demo.example", password_hash=hash_password("pw"))
    db.add(StudentProfile(user_id=student.id, exam_year=2027))
    db.add(StudentSubject(student_user_id=student.id, subject_code="english"))
    db.commit()
    return student


def _token(client):
    return client.post("/auth/login", json={"email": "student@demo.example", "password": "pw"}).json()["access_token"]


def test_student_can_start_placement_and_get_paper(client, db_session):
    _seed_student(db_session)
    token = _token(client)
    start = client.post("/student/placement/start", headers={"Authorization": f"Bearer {token}"})
    assert start.status_code == 200

    papers = db_session.execute(select(PlacementPaper)).scalars().all()
    assert len(papers) == 1
