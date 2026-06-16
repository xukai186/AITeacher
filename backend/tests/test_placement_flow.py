from sqlalchemy import select

from app.auth.security import hash_password
from app.models import DailyTask, MasterPlan, MasterPlanVersion, MasterySnapshot, PlacementPaper, PlacementQuestion, PlacementResult, StudentProfile, StudentSubject, SubjectPlan, SubjectPlanVersion, UserRole, WrongBookItem
from tests.factories import make_org, make_user
from tests.paper_gen_job_helpers import start_placement_and_wait


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
    start_placement_and_wait(client, token, db_session=db_session)

    papers = db_session.execute(select(PlacementPaper)).scalars().all()
    assert len(papers) == 1


def test_student_can_submit_placement_and_get_result(client, db_session):
    _seed_student(db_session)
    token = _token(client)
    start_placement_and_wait(client, token, db_session=db_session)

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
    assert db_session.query(MasterPlan).count() == 1
    assert db_session.query(MasterPlanVersion).count() == 1
    assert db_session.query(SubjectPlan).count() >= 1
    assert db_session.query(SubjectPlanVersion).count() >= 1
    assert db_session.query(DailyTask).count() >= 1


def test_placement_submit_with_existing_mastery_snapshot(client, db_session):
    """Orphan mastery snapshot (e.g. after question regen) must not block submit."""
    student = _seed_student(db_session)
    token = _token(client)
    start = start_placement_and_wait(
        client,
        token,
        {"subject_code": "english"},
        db_session=db_session,
    )
    paper_id = start["subjects"][0]["paper_id"]

    from app.models import MasterySnapshot

    db_session.add(
        MasterySnapshot(
            student_user_id=student.id,
            subject_code="english",
            version=1,
            mastery_json={"old": 1},
        )
    )
    db_session.commit()

    questions = (
        db_session.execute(select(PlacementQuestion).where(PlacementQuestion.paper_id == paper_id))
        .scalars()
        .all()
    )
    submit = client.post(
        f"/student/placement/{paper_id}/submit",
        json={
            "answers": [
                {"question_id": str(q.id), "content": q.answer_key}
                for q in questions
            ]
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert submit.status_code == 200
    snap = db_session.execute(
        select(MasterySnapshot).where(
            MasterySnapshot.student_user_id == student.id,
            MasterySnapshot.subject_code == "english",
        )
    ).scalar_one()
    assert "old" not in snap.mastery_json


def test_wrong_book_ingested_after_placement_submit(client, db_session):
    _seed_student(db_session)
    token = _token(client)
    start_placement_and_wait(client, token, db_session=db_session)

    paper_id = client.get("/student/placement", headers={"Authorization": f"Bearer {token}"}).json()[0]["id"]

    questions = (
        db_session.execute(select(PlacementQuestion).where(PlacementQuestion.paper_id == paper_id))
        .scalars()
        .all()
    )
    assert questions

    payload = {"answers": [{"question_id": str(q.id), "content": "Z"} for q in questions]}
    submit = client.post(
        f"/student/placement/{paper_id}/submit",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert submit.status_code == 200

    items = db_session.execute(select(WrongBookItem).where(WrongBookItem.source_type == "placement")).scalars().all()
    assert len(items) > 0
