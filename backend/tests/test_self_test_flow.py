from sqlalchemy import select

from app.auth.security import hash_password
from app.models import SelfTestGrade, SelfTestPaper, SelfTestQuestion, SelfTestSubmission, StudentProfile, StudentSubject, UserRole
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


def test_student_can_submit_self_test_and_get_grade(client, db_session):
    _seed_student(db_session)
    token = _token(client)

    gen = client.post(
        "/student/self-tests/generate",
        json={"subject_code": "english"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert gen.status_code == 200
    paper_id = gen.json()["id"]

    paper = client.get(
        f"/student/self-tests/{paper_id}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    answers = [{"question_id": q["id"], "content": "A"} for q in paper["questions"]]

    submit = client.post(
        f"/student/self-tests/{paper_id}/submit",
        json={"answers": answers},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert submit.status_code == 200
    out = submit.json()
    assert out["submission_id"]
    assert out["total_score"] >= 0

    assert db_session.query(SelfTestSubmission).count() == 1
    assert db_session.query(SelfTestGrade).count() == 1


def test_student_can_submit_subjective_self_test_question(client, db_session, monkeypatch):
    _seed_student(db_session)
    token = _token(client)

    called = {"ok": False}
    import app.services.model_gateway as mg

    def fake_generate(self, req):
        assert req.scene == "grading"
        called["ok"] = True
        return mg.ModelGatewayResponse(text='{"score": 1, "feedback": "ok"}')

    monkeypatch.setattr(mg.ModelGateway, "generate", fake_generate, raising=True)

    gen = client.post(
        "/student/self-tests/generate",
        json={"subject_code": "english"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert gen.status_code == 200
    paper_id = gen.json()["id"]

    # flip first question to subjective for this test
    q = db_session.execute(select(SelfTestQuestion).limit(1)).scalar_one()
    q.q_type = "short_answer"
    q.answer_key = None
    q.rubric_json = {"expected": ["point1", "point2"]}
    db_session.commit()

    paper = client.get(
        f"/student/self-tests/{paper_id}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    answers = [{"question_id": q["id"], "content": "my answer"} for q in paper["questions"]]

    submit = client.post(
        f"/student/self-tests/{paper_id}/submit",
        json={"answers": answers},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert submit.status_code == 200
    out = submit.json()
    assert out["detail_json"]
    assert called["ok"] is True

