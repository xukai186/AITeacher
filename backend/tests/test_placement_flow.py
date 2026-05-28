from sqlalchemy import select

from app.auth.security import hash_password
from app.models import MasterySnapshot, PlacementPaper, PlacementQuestion, PlacementResult, StudentProfile, StudentSubject, UserRole
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


def test_student_can_submit_placement_and_get_result(client, db_session):
    _seed_student(db_session)
    token = _token(client)
    start = client.post("/student/placement/start", headers={"Authorization": f"Bearer {token}"})
    assert start.status_code == 200

    paper_id = client.get("/student/placement", headers={"Authorization": f"Bearer {token}"}).json()[0]["id"]
    paper = client.get(f"/student/placement/{paper_id}", headers={"Authorization": f"Bearer {token}"}).json()

    questions = (
        db_session.execute(select(PlacementQuestion).where(PlacementQuestion.paper_id == paper_id))
        .scalars()
        .all()
    )
    assert questions

    payload = {
        "answers": [
            {"question_id": str(q.id), "content": q.answer_key}
            for q in questions
        ]
    }
    submit = client.post(
        f"/student/placement/{paper_id}/submit",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert submit.status_code == 200
    out = submit.json()
    assert out["paper_id"] == paper_id
    assert out["total_score"] > 0
    assert db_session.query(PlacementResult).count() == 1
    assert db_session.query(MasterySnapshot).count() == 1
