import json
import uuid

from sqlalchemy import select

from app.auth.security import hash_password
from app.models import (
    ModelPolicy,
    SelfTestQuestion,
    SyllabusNode,
    UserRole,
    WrongBookItem,
)
from app.seed_syllabus import seed_minimal_syllabus
from app.services.paper_gen import PaperGenService
from app.services.self_test import SelfTestService
from tests.factories import make_org, make_user


def _seed_student_with_syllabus(db):
    org = make_org(db)
    student = make_user(
        db,
        org,
        role=UserRole.student,
        email="pg@demo.example",
        password_hash=hash_password("pw"),
    )
    seed_minimal_syllabus(db)
    db.commit()
    return org, student


def test_paper_gen_mock_targets_weak_nodes(db_session):
    org, student = _seed_student_with_syllabus(db_session)
    node = db_session.execute(
        select(SyllabusNode).where(SyllabusNode.subject_code == "english").limit(1)
    ).scalar_one()
    db_session.add(
        WrongBookItem(
            student_user_id=student.id,
            subject_code="english",
            knowledge_node_id=node.id,
            source_type="self_test",
            source_id=uuid.uuid4(),
            question_snapshot_json={"stem": "x"},
            answer_snapshot_json={"content": "A"},
            correct_snapshot_json={"answer_key": "B"},
        )
    )
    db_session.add(
        ModelPolicy(
            org_id=org.id,
            scene="paper_gen",
            provider="mock",
            model="mock-v1",
            params={},
        )
    )
    db_session.commit()

    questions = PaperGenService().generate_for_self_test(
        db_session,
        org_id=org.id,
        student_user_id=student.id,
        subject_code="english",
        question_count=3,
    )

    assert len(questions) == 3
    assert any(node.name in q.stem for q in questions)


def test_paper_gen_openai_compat_uses_gateway(db_session, monkeypatch):
    org, student = _seed_student_with_syllabus(db_session)
    node = db_session.execute(
        select(SyllabusNode).where(SyllabusNode.subject_code == "english").limit(1)
    ).scalar_one()
    db_session.add(
        ModelPolicy(
            org_id=org.id,
            scene="paper_gen",
            provider="openai_compat",
            model="gpt-test",
            params={"base_url": "https://example.invalid", "api_key": "k"},
        )
    )
    db_session.commit()

    payload = {
        "questions": [
            {
                "seq": 1,
                "knowledge_node_id": str(node.id),
                "q_type": "single_choice",
                "stem": "AI 组卷：阅读理解主旨题",
                "choices": [
                    {"key": "A", "text": "选项A"},
                    {"key": "B", "text": "选项B"},
                    {"key": "C", "text": "选项C"},
                    {"key": "D", "text": "选项D"},
                ],
                "answer_key": "B",
                "points": 1,
            }
        ]
    }

    import app.services.model_gateway as mg

    def fake_generate(self, req):
        assert req.scene == "paper_gen"
        assert req.provider == "openai_compat"
        return mg.ModelGatewayResponse(text=json.dumps(payload, ensure_ascii=False))

    monkeypatch.setattr(mg.ModelGateway, "generate", fake_generate)

    questions = PaperGenService().generate_for_self_test(
        db_session,
        org_id=org.id,
        student_user_id=student.id,
        subject_code="english",
        question_count=1,
    )

    assert len(questions) == 1
    assert questions[0].stem.startswith("AI 组卷")


def test_paper_gen_falls_back_when_llm_json_invalid(db_session, monkeypatch):
    org, student = _seed_student_with_syllabus(db_session)
    db_session.add(
        ModelPolicy(
            org_id=org.id,
            scene="paper_gen",
            provider="openai_compat",
            model="gpt-test",
            params={"base_url": "https://example.invalid", "api_key": "k"},
        )
    )
    db_session.commit()

    import app.services.model_gateway as mg

    def fake_generate(self, req):
        return mg.ModelGatewayResponse(text="not json")

    monkeypatch.setattr(mg.ModelGateway, "generate", fake_generate)

    questions = PaperGenService().generate_for_self_test(
        db_session,
        org_id=org.id,
        student_user_id=student.id,
        subject_code="english",
        question_count=5,
    )

    assert len(questions) == 5
    assert all(q.q_type == "single_choice" for q in questions)


def test_self_test_generate_uses_paper_gen_policy(db_session):
    org, student = _seed_student_with_syllabus(db_session)
    from app.models import StudentSubject

    db_session.add(StudentSubject(student_user_id=student.id, subject_code="english", enabled=True))
    db_session.add(
        ModelPolicy(
            org_id=org.id,
            scene="paper_gen",
            provider="mock",
            model="mock-v1",
            params={},
        )
    )
    db_session.commit()

    paper = SelfTestService.generate(
        db_session, student.id, "english", skip_eligibility=True
    )
    questions = (
        db_session.execute(select(SelfTestQuestion).where(SelfTestQuestion.paper_id == paper.id))
        .scalars()
        .all()
    )
    assert len(questions) == 10
    assert paper.source == "ai"
