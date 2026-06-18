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
from app.models import PlacementPaper, PlacementQuestion, StudentProfile, StudentSubject
from app.services.paper_gen import PaperGenService
from app.services.placement import PlacementService
from app.services.self_test import SelfTestService
from tests.factories import make_org, make_user
from tests.paper_gen_job_helpers import finish_paper_gen_jobs


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


def test_paper_gen_placement_mock_uses_syllabus_and_past_exam_context(db_session):
    org, student = _seed_student_with_syllabus(db_session)
    db_session.add(StudentProfile(user_id=student.id, exam_year=2027))
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

    questions = PaperGenService().generate_for_placement(
        db_session,
        org_id=org.id,
        student_user_id=student.id,
        subject_code="english",
        question_count=3,
    )

    assert len(questions) == 3
    assert all("模拟摸底" in q.stem for q in questions)
    assert all("2027考纲" in q.stem for q in questions)
    assert all("参照2024年卷" in q.stem for q in questions)
    assert questions[0].stem.startswith("【模拟摸底·完形填空")
    assert questions[2].stem.startswith("【模拟摸底·阅读理解")


def test_paper_gen_placement_llm_prompt_includes_syllabus_and_past_exams(db_session, monkeypatch):
    org, student = _seed_student_with_syllabus(db_session)
    db_session.add(StudentProfile(user_id=student.id, exam_year=2027))
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

    import app.services.model_gateway as mg

    captured: dict[str, str] = {}

    def fake_generate(self, req):
        captured["prompt"] = req.prompt
        payload = {
            "questions": [
                {
                    "seq": 1,
                    "knowledge_node_id": str(node.id),
                    "q_type": "single_choice",
                    "stem": "AI 摸底：结合考纲与真题风格",
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
        return mg.ModelGatewayResponse(text=json.dumps(payload, ensure_ascii=False))

    monkeypatch.setattr(mg.ModelGateway, "generate", fake_generate)

    questions = PaperGenService().generate_for_placement(
        db_session,
        org_id=org.id,
        student_user_id=student.id,
        subject_code="english",
        question_count=1,
    )

    assert len(questions) == 1
    prompt = captured["prompt"]
    assert "2027" in prompt
    assert "当年考试大纲" in prompt
    assert "往年真题卷结构" in prompt
    assert "完形填空" in prompt
    assert "2024真题" in prompt or "2023真题" in prompt


def test_paper_gen_placement_mock_uses_placement_stem(db_session):
    org, student = _seed_student_with_syllabus(db_session)
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

    questions = PaperGenService().generate_for_placement(
        db_session,
        org_id=org.id,
        student_user_id=student.id,
        subject_code="english",
        question_count=3,
    )

    assert len(questions) == 3
    assert all("模拟摸底" in q.stem for q in questions)


def test_placement_start_uses_paper_gen_policy(db_session):
    org, student = _seed_student_with_syllabus(db_session)
    from app.models import StudentProfile

    db_session.add(StudentProfile(user_id=student.id, exam_year=2027))
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

    PlacementService.start(db_session, student.id, subject_code="english")
    finish_paper_gen_jobs(db_session)
    db_session.commit()
    paper = db_session.execute(select(PlacementPaper)).scalar_one()
    questions = (
        db_session.execute(select(PlacementQuestion).where(PlacementQuestion.paper_id == paper.id))
        .scalars()
        .all()
    )
    assert len(questions) == 10
    assert all("模拟摸底" in q.stem for q in questions)


def test_placement_start_skips_regeneration_for_existing_llm_questions(db_session):
    org, student = _seed_student_with_syllabus(db_session)
    from app.models import PlacementPaper, PlacementQuestion, StudentProfile, StudentSubject

    db_session.add(StudentProfile(user_id=student.id, exam_year=2027))
    db_session.add(StudentSubject(student_user_id=student.id, subject_code="english", enabled=True))
    paper = PlacementPaper(student_user_id=student.id, subject_code="english", status="ready")
    db_session.add(paper)
    db_session.flush()
    db_session.add(
        PlacementQuestion(
            paper_id=paper.id,
            seq=1,
            q_type="single_choice",
            stem="LLM generated reading comprehension question",
            choices_json=[{"key": "A", "text": "A"}],
            answer_key="A",
            points=1,
        )
    )
    db_session.commit()

    PlacementService.start(db_session, student.id, subject_code="english")
    finish_paper_gen_jobs(db_session)
    db_session.commit()
    questions = (
        db_session.execute(select(PlacementQuestion).where(PlacementQuestion.paper_id == paper.id))
        .scalars()
        .all()
    )
    assert len(questions) == 1
    assert questions[0].stem == "LLM generated reading comprehension question"


def test_placement_start_regenerates_unsubmitted_paper(db_session):
    org, student = _seed_student_with_syllabus(db_session)
    from app.models import PlacementPaper, PlacementQuestion, StudentProfile, StudentSubject

    db_session.add(StudentProfile(user_id=student.id, exam_year=2027))
    db_session.add(StudentSubject(student_user_id=student.id, subject_code="english", enabled=True))
    paper = PlacementPaper(student_user_id=student.id, subject_code="english", status="ready")
    db_session.add(paper)
    db_session.flush()
    db_session.add(
        PlacementQuestion(
            paper_id=paper.id,
            seq=1,
            q_type="single_choice",
            stem="【写作】请选择最符合考纲要求的选项（第1题）",
            choices_json=[{"key": "A", "text": "A"}],
            answer_key="A",
            points=1,
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

    PlacementService.start(db_session, student.id, subject_code="english")
    finish_paper_gen_jobs(db_session)
    db_session.commit()
    questions = (
        db_session.execute(select(PlacementQuestion).where(PlacementQuestion.paper_id == paper.id))
        .scalars()
        .all()
    )
    assert len(questions) == 10
    assert all("模拟摸底" in q.stem for q in questions)


def test_placement_start_keeps_submitted_paper(db_session):
    org, student = _seed_student_with_syllabus(db_session)
    from app.models import (
        PlacementPaper,
        PlacementQuestion,
        PlacementSubmission,
        StudentProfile,
        StudentSubject,
    )

    db_session.add(StudentProfile(user_id=student.id, exam_year=2027))
    db_session.add(StudentSubject(student_user_id=student.id, subject_code="english", enabled=True))
    paper = PlacementPaper(student_user_id=student.id, subject_code="english", status="ready")
    db_session.add(paper)
    db_session.flush()
    db_session.add(
        PlacementQuestion(
            paper_id=paper.id,
            seq=1,
            q_type="single_choice",
            stem="【写作】旧题保留",
            choices_json=[{"key": "A", "text": "A"}],
            answer_key="A",
            points=1,
        )
    )
    db_session.add(
        PlacementSubmission(
            paper_id=paper.id,
            student_user_id=student.id,
            status="submitted",
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

    PlacementService.start(db_session, student.id, subject_code="english")
    finish_paper_gen_jobs(db_session)
    db_session.commit()
    questions = (
        db_session.execute(select(PlacementQuestion).where(PlacementQuestion.paper_id == paper.id))
        .scalars()
        .all()
    )
    assert len(questions) == 1
    assert questions[0].stem == "【写作】旧题保留"


def test_paper_gen_llm_batches_large_paper(db_session):
    import re

    from app.services.model_gateway import ModelGateway, ModelGatewayRequest, ModelGatewayResponse

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

    class BatchGateway(ModelGateway):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def generate(self, req: ModelGatewayRequest) -> ModelGatewayResponse:
            self.calls += 1
            batch_match = re.search(
                r"本批次需生成的题目（按卷面顺序）：\n(\[.*?\])\n",
                req.prompt,
                re.DOTALL,
            )
            if batch_match:
                slots = json.loads(batch_match.group(1))
                count = len(slots)
                node_ids = [slot["knowledge_node_id"] for slot in slots]
            else:
                match = re.search(r"需要题目数量：(\d+)", req.prompt)
                count = int(match.group(1)) if match else 5
                node_ids = [str(node.id)] * count
            payload = {
                "questions": [
                    {
                        "seq": i,
                        "knowledge_node_id": node_ids[i - 1],
                        "q_type": "single_choice",
                        "stem": f"LLM 题 {i}",
                        "choices": [{"key": k, "text": k} for k in ("A", "B", "C", "D")],
                        "answer_key": "A",
                        "points": 1,
                    }
                    for i in range(1, count + 1)
                ]
            }
            return ModelGatewayResponse(text=json.dumps(payload, ensure_ascii=False))

    gateway = BatchGateway()
    svc = PaperGenService(model_gateway=gateway)
    questions = svc.generate_for_placement(
        db_session,
        org_id=org.id,
        student_user_id=student.id,
        subject_code="english",
        question_count=None,
    )
    assert gateway.calls == 4
    assert len(questions) == 10
    assert all("LLM 题" in q.stem for q in questions)


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

    paper, gen_job_id = SelfTestService.generate(
        db_session, student.id, "english", skip_eligibility=True
    )
    finish_paper_gen_jobs(db_session)
    db_session.commit()
    questions = (
        db_session.execute(select(SelfTestQuestion).where(SelfTestQuestion.paper_id == paper.id))
        .scalars()
        .all()
    )
    assert len(questions) == 10
    assert paper.source == "ai"
