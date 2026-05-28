from sqlalchemy import select

from app.auth.security import hash_password
from app.models import WrongBookItem, StudentProfile, StudentSubject, UserRole
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


def test_wrong_book_ingested_after_self_test_submit(client, db_session):
    _seed_student(db_session)
    token = _token(client)

    gen = client.post(
        "/student/self-tests/generate",
        json={"subject_code": "english"},
        headers={"Authorization": f"Bearer {token}"},
    )
    paper_id = gen.json()["id"]
    paper = client.get(
        f"/student/self-tests/{paper_id}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()

    # intentionally wrong answers
    answers = [{"question_id": q["id"], "content": "Z"} for q in paper["questions"]]
    submit = client.post(
        f"/student/self-tests/{paper_id}/submit",
        json={"answers": answers},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert submit.status_code == 200

    items = db_session.execute(select(WrongBookItem)).scalars().all()
    assert len(items) > 0


def test_student_can_list_wrong_book_items(client, db_session):
    _seed_student(db_session)
    token = _token(client)

    gen = client.post(
        "/student/self-tests/generate",
        json={"subject_code": "english"},
        headers={"Authorization": f"Bearer {token}"},
    )
    paper_id = gen.json()["id"]
    paper = client.get(
        f"/student/self-tests/{paper_id}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()

    answers = [{"question_id": q["id"], "content": "Z"} for q in paper["questions"]]
    submit = client.post(
        f"/student/self-tests/{paper_id}/submit",
        json={"answers": answers},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert submit.status_code == 200

    resp = client.get("/student/wrong-book?subject_code=english", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) > 0

