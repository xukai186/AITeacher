from sqlalchemy import select

from app.auth.security import hash_password
from app.models import ModelPolicy, QuestionBankItem, SelfTestGrade, SelfTestPaper, SelfTestQuestion, SelfTestSubmission, StudentProfile, StudentSubject, UserRole
from app.services.paper_gen import DEFAULT_QUESTION_COUNT, PaperGenService
from tests.factories import make_org, make_user
from tests.paper_gen_job_helpers import finish_paper_gen_jobs, generate_self_test_and_wait


def _seed_student(db):
    org = make_org(db)
    make_user(db, org, role=UserRole.org_admin)
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

    gen = generate_self_test_and_wait(client, token, db_session=db_session)

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


def test_self_test_job_uses_full_org_bank_without_llm(client, db_session, monkeypatch):
    student = _seed_student(db_session)
    for index in range(DEFAULT_QUESTION_COUNT):
        db_session.add(
            QuestionBankItem(
                scope="org",
                org_id=student.org_id,
                subject_code="english",
                knowledge_node_id=None,
                q_type="single_choice",
                stem=f"Bank question {index}",
                choices_json=[{"key": "A", "text": "answer"}],
                answer_key="A",
                analysis_text=None,
                difficulty=2,
                source_type="admin_manual",
                status="active",
                created_by=student.id,
            )
        )
    db_session.commit()

    def fail_generate(*_args, **_kwargs):
        raise AssertionError("paper generation should not run for a full bank")

    monkeypatch.setattr(
        PaperGenService,
        "generate_prepared_self_test",
        fail_generate,
    )

    token = _token(client)
    generated = generate_self_test_and_wait(client, token, db_session=db_session)
    paper = db_session.get(SelfTestPaper, generated["id"])
    questions = db_session.execute(
        select(SelfTestQuestion).where(SelfTestQuestion.paper_id == paper.id)
    ).scalars().all()

    assert paper.status == "ready"
    assert len(questions) == DEFAULT_QUESTION_COUNT
    assert all(question.bank_item_id is not None for question in questions)
    assert {question.selection_source for question in questions} == {"bank_org"}


def test_student_can_submit_self_test_and_get_grade(client, db_session):
    _seed_student(db_session)
    token = _token(client)

    gen = generate_self_test_and_wait(client, token, db_session=db_session)
    paper_id = gen["id"]

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

    submission_id = out["submission_id"]
    grade = client.get(
        f"/student/self-tests/submissions/{submission_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert grade.status_code == 200
    assert grade.json()["submission_id"] == submission_id


def test_student_can_submit_subjective_self_test_question(client, db_session, monkeypatch):
    student = _seed_student(db_session)
    token = _token(client)

    db_session.add(
        ModelPolicy(
            org_id=student.org_id,
            scene="grading",
            provider="openai_compat",
            model="gpt-test",
            params={"base_url": "https://example.invalid", "api_key": "k"},
        )
    )
    db_session.commit()

    called = {"ok": False}
    import app.services.model_gateway as mg

    def fake_generate(self, req):
        assert req.scene == "grading"
        assert req.provider == "openai_compat"
        assert req.model == "gpt-test"
        called["ok"] = True
        return mg.ModelGatewayResponse(text='{"score": 1, "feedback": "ok"}')

    monkeypatch.setattr(mg.ModelGateway, "generate", fake_generate, raising=True)

    gen = generate_self_test_and_wait(client, token, db_session=db_session)
    paper_id = gen["id"]

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

