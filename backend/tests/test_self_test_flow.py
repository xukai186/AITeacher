from sqlalchemy import select

from app.auth.security import hash_password
from app.models import SelfTestPaper, SelfTestQuestion, StudentProfile, StudentSubject, UserRole
from tests.factories import make_org, make_user


def _seed_student(db):
    org = make_org(db)
    student = make_user(
        db,
        org,
        role=UserRole.student,
        email="student@demo.example",
        password_hash=hash_password("pw"),
    )
    db.add(StudentProfile(user_id=student.id, exam_year=2027))
    db.add(StudentSubject(student_user_id=student.id, subject_code="english"))
    db.commit()
    return student


def _token(client):
    return client.post("/auth/login", json={"email": "student@demo.example", "password": "pw"}).json()[
        "access_token"
    ]


def test_student_can_generate_list_and_get_self_test_paper(client, db_session):
    _seed_student(db_session)
    token = _token(client)

    gen = client.post(
        "/student/self-tests/generate",
        json={"subject_code": "english"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert gen.status_code == 200

    papers = client.get("/student/self-tests", headers={"Authorization": f"Bearer {token}"})
    assert papers.status_code == 200
    paper_id = papers.json()[0]["id"]

    detail = client.get(
        f"/student/self-tests/{paper_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail.status_code == 200
    assert len(detail.json()["questions"]) > 0

    # verify DB side effects
    db_papers = db_session.execute(select(SelfTestPaper)).scalars().all()
    assert len(db_papers) == 1
    db_questions = db_session.execute(select(SelfTestQuestion)).scalars().all()
    assert len(db_questions) > 0

