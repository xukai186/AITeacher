import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.auth.security import hash_password
from app.models import (
    ModelPolicy,
    SelfTestQuestion,
    StudentExamProfile,
    SyllabusNode,
    UserRole,
    WrongBookItem,
)
from app.seed_exam_majors import seed_exam_majors
from app.seed_syllabus import seed_minimal_syllabus
from app.models import PlacementPaper, PlacementQuestion, StudentProfile, StudentSubject
from app.services.paper_gen import PaperGenService
from app.services.placement import PlacementService
from app.services.self_test import SelfTestService
from tests.exam_profile_helpers import add_complete_exam_profile
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
    add_complete_exam_profile(db, student.id)
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
    assert questions[2].stem.startswith("【模拟摸底·完形填空")


def test_parse_llm_questions_for_slots_accepts_fill_blank(db_session):
    from app.models import StudentProfile
    from app.services.placement_paper_context import (
        build_placement_context,
        build_placement_slots,
        leaf_nodes_for_placement,
    )

    org, student = _seed_student_with_syllabus(db_session)
    db_session.add(StudentProfile(user_id=student.id, exam_year=2027))
    db_session.commit()

    ctx = build_placement_context(
        db_session, student_user_id=student.id, subject_code="math"
    )
    leaves = leaf_nodes_for_placement(
        db_session, subject_code="math", exam_year=ctx.exam_year
    )
    fill_slot = next(
        slot
        for slot in build_placement_slots(db_session, ctx, leaves, [])
        if slot.q_type == "fill_blank"
    )

    raw = json.dumps(
        {
            "questions": [
                {
                    "seq": fill_slot.seq,
                    "knowledge_node_id": str(fill_slot.knowledge_node.id),
                    "q_type": "fill_blank",
                    "stem": "设 f(x)=x^2，则 f'(1)= ____",
                    "answer_key": "2",
                }
            ]
        },
        ensure_ascii=False,
    )
    parsed = PaperGenService()._parse_llm_questions_for_slots(raw, slots=[fill_slot])
    assert len(parsed) == 1
    assert parsed[0].stem.startswith("设 f(x)")
    assert parsed[0].answer_key == "2"
    assert parsed[0].choices_json is None


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
    db_session.add(StudentSubject(student_user_id=student.id, subject_code="math", enabled=True))
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

    PlacementService.start(db_session, student.id, subject_code="math")
    finish_paper_gen_jobs(db_session)
    db_session.commit()
    paper = db_session.execute(select(PlacementPaper)).scalar_one()
    questions = (
        db_session.execute(select(PlacementQuestion).where(PlacementQuestion.paper_id == paper.id))
        .scalars()
        .all()
    )
    assert len(questions) == 22
    assert all("模拟摸底" in q.stem for q in questions)
    assert any(q.q_type == "fill_blank" for q in questions)
    assert any(q.q_type == "short_answer" for q in questions)


def test_placement_start_skips_regeneration_for_existing_llm_questions(db_session):
    org, student = _seed_student_with_syllabus(db_session)
    from app.models import PlacementPaper, PlacementQuestion, StudentProfile, StudentSubject
    from app.services.placement_paper_context import (
        build_placement_context,
        build_placement_slots,
        leaf_nodes_for_placement,
    )

    db_session.add(StudentProfile(user_id=student.id, exam_year=2027))
    db_session.add(StudentSubject(student_user_id=student.id, subject_code="math", enabled=True))
    paper = PlacementPaper(student_user_id=student.id, subject_code="math", status="ready")
    db_session.add(paper)
    db_session.flush()

    ctx = build_placement_context(
        db_session, student_user_id=student.id, subject_code="math"
    )
    leaves = leaf_nodes_for_placement(
        db_session, subject_code="math", exam_year=ctx.exam_year
    )
    for slot in build_placement_slots(db_session, ctx, leaves, []):
        choices = (
            [{"key": "A", "text": "A"}]
            if slot.q_type in ("single_choice", "multi_choice")
            else None
        )
        db_session.add(
            PlacementQuestion(
                paper_id=paper.id,
                seq=slot.seq,
                q_type=slot.q_type,
                stem=f"LLM generated question {slot.seq}",
                choices_json=choices,
                answer_key="A",
                points=slot.points,
            )
        )
    db_session.commit()

    PlacementService.start(db_session, student.id, subject_code="math")
    finish_paper_gen_jobs(db_session)
    db_session.commit()
    questions = (
        db_session.execute(select(PlacementQuestion).where(PlacementQuestion.paper_id == paper.id))
        .scalars()
        .all()
    )
    assert len(questions) == 22
    assert questions[0].stem == "LLM generated question 1"


def test_placement_start_regenerates_llm_paper_with_wrong_count(db_session):
    org, student = _seed_student_with_syllabus(db_session)
    from app.models import PlacementPaper, PlacementQuestion, StudentProfile, StudentSubject

    db_session.add(StudentProfile(user_id=student.id, exam_year=2027))
    db_session.add(StudentSubject(student_user_id=student.id, subject_code="math", enabled=True))
    db_session.add(
        ModelPolicy(
            org_id=org.id,
            scene="paper_gen",
            provider="mock",
            model="mock-v1",
            params={},
        )
    )
    paper = PlacementPaper(student_user_id=student.id, subject_code="math", status="ready")
    db_session.add(paper)
    db_session.flush()
    for seq in range(1, 11):
        db_session.add(
            PlacementQuestion(
                paper_id=paper.id,
                seq=seq,
                q_type="single_choice",
                stem=f"设函数f(x)在x=0处连续（第{seq}题）",
                choices_json=[{"key": "A", "text": "A"}],
                answer_key="A",
                points=4,
            )
        )
    db_session.commit()

    PlacementService.start(db_session, student.id, subject_code="math")
    finish_paper_gen_jobs(db_session)
    db_session.commit()
    questions = (
        db_session.execute(select(PlacementQuestion).where(PlacementQuestion.paper_id == paper.id))
        .scalars()
        .all()
    )
    assert len(questions) == 22
    assert any(q.q_type == "fill_blank" for q in questions)


def test_placement_start_regenerates_unsubmitted_paper(db_session):
    org, student = _seed_student_with_syllabus(db_session)
    from app.models import PlacementPaper, PlacementQuestion, StudentProfile, StudentSubject

    db_session.add(StudentProfile(user_id=student.id, exam_year=2027))
    db_session.add(StudentSubject(student_user_id=student.id, subject_code="math", enabled=True))
    paper = PlacementPaper(student_user_id=student.id, subject_code="math", status="ready")
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

    PlacementService.start(db_session, student.id, subject_code="math")
    finish_paper_gen_jobs(db_session)
    db_session.commit()
    questions = (
        db_session.execute(select(PlacementQuestion).where(PlacementQuestion.paper_id == paper.id))
        .scalars()
        .all()
    )
    assert len(questions) == 22
    assert all("模拟摸底" in q.stem for q in questions)
    assert any(q.q_type == "fill_blank" for q in questions)
    assert any(q.q_type == "short_answer" for q in questions)


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
    db_session.add(StudentSubject(student_user_id=student.id, subject_code="math", enabled=True))
    paper = PlacementPaper(student_user_id=student.id, subject_code="math", status="ready")
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

    PlacementService.start(db_session, student.id, subject_code="math")
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
        subject_code="math",
        question_count=None,
    )
    assert gateway.calls >= 8
    assert len(questions) == 22
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


def test_placement_llm_batch_retries_missing_slots(db_session, monkeypatch):
    org, student = _seed_student_with_syllabus(db_session)
    db_session.add(StudentProfile(user_id=student.id, exam_year=2027))
    db_session.add(StudentSubject(student_user_id=student.id, subject_code="math", enabled=True))
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

    from app.services.placement_paper_context import (
        build_placement_context,
        build_placement_slots,
        leaf_nodes_for_placement,
    )

    ctx = build_placement_context(
        db_session, student_user_id=student.id, subject_code="math"
    )
    leaves = leaf_nodes_for_placement(
        db_session, subject_code="math", exam_year=ctx.exam_year
    )
    slots = build_placement_slots(db_session, ctx, leaves, [])[:3]
    svc = PaperGenService()
    calls = {"n": 0}

    def fake_call(self, provider, model, params, *, subject_code, slots, placement_context):
        calls["n"] += 1
        if len(slots) == 3:
            return json.dumps(
                {
                    "questions": [
                        {"stem": "batch q1", "answer_key": "A", "choices": [{"key": "A", "text": "a"}]},
                        {"stem": "batch q2", "answer_key": "A", "choices": [{"key": "A", "text": "a"}]},
                    ]
                }
            )
        assert len(slots) == 1
        slot = slots[0]
        if slot.q_type in ("single_choice", "multi_choice"):
            return json.dumps(
                {
                    "questions": [
                        {
                            "stem": f"single q{slot.seq}",
                            "answer_key": "A",
                            "choices": [{"key": "A", "text": "a"}],
                        }
                    ]
                }
            )
        return json.dumps(
            {"questions": [{"stem": f"single q{slot.seq}", "answer_key": "ans"}]}
        )

    monkeypatch.setattr(PaperGenService, "_call_llm_for_slots", fake_call)

    out = svc._generate_with_llm_batches_from_slots(
        "openai_compat",
        "gpt-test",
        {},
        student_user_id=student.id,
        subject_code="math",
        slots=slots,
        placement_context=ctx,
    )

    assert len(out) == 3
    assert out[0].stem == "batch q1"
    assert out[1].stem == "batch q2"
    assert "single q3" in out[2].stem
    assert calls["n"] == 2


def test_placement_start_regenerates_when_llm_paper_has_mock_stems(db_session, monkeypatch):
    org, student = _seed_student_with_syllabus(db_session)
    db_session.add(StudentProfile(user_id=student.id, exam_year=2027))
    db_session.add(StudentSubject(student_user_id=student.id, subject_code="math", enabled=True))
    db_session.add(
        ModelPolicy(
            org_id=org.id,
            scene="paper_gen",
            provider="openai_compat",
            model="mock-v1",
            params={},
        )
    )
    paper = PlacementPaper(student_user_id=student.id, subject_code="math", status="ready")
    db_session.add(paper)
    db_session.flush()

    from app.services.placement_paper_context import (
        build_placement_context,
        build_placement_slots,
        leaf_nodes_for_placement,
    )

    ctx = build_placement_context(
        db_session, student_user_id=student.id, subject_code="math"
    )
    leaves = leaf_nodes_for_placement(
        db_session, subject_code="math", exam_year=ctx.exam_year
    )
    for slot in build_placement_slots(db_session, ctx, leaves, []):
        stem = (
            f"【模拟摸底·解答题·2027考纲·概率】第{slot.seq}题：请作答"
            if slot.seq == 19
            else f"LLM generated question {slot.seq}"
        )
        choices = (
            [{"key": "A", "text": "A"}]
            if slot.q_type in ("single_choice", "multi_choice")
            else None
        )
        db_session.add(
            PlacementQuestion(
                paper_id=paper.id,
                seq=slot.seq,
                q_type=slot.q_type,
                stem=stem,
                choices_json=choices,
                answer_key="A",
                points=slot.points,
            )
        )
    db_session.commit()

    import app.services.model_gateway as mg

    def fake_generate(self, req):
        return mg.ModelGatewayResponse(
            text=json.dumps(
                {
                    "questions": [
                        {
                            "stem": "regenerated",
                            "answer_key": "A",
                            "choices": [{"key": "A", "text": "a"}],
                        }
                    ]
                }
            )
        )

    monkeypatch.setattr(mg.ModelGateway, "generate", fake_generate)

    PlacementService.start(db_session, student.id, subject_code="math")
    finish_paper_gen_jobs(db_session)
    db_session.commit()

    questions = (
        db_session.execute(select(PlacementQuestion).where(PlacementQuestion.paper_id == paper.id))
        .scalars()
        .all()
    )
    assert len(questions) == 22
    assert not any("【模拟摸底·" in q.stem for q in questions)


def test_self_test_prompt_excludes_cet_and_math_mastery(db_session, monkeypatch):
    org, student = _seed_student_with_syllabus(db_session)
    node = db_session.execute(
        select(SyllabusNode).where(SyllabusNode.subject_code == "english").limit(1)
    ).scalar_one()
    profile = db_session.get(StudentExamProfile, student.id)
    profile.cet_status = "cet4"
    profile.cet_score = 460
    profile.math_mastery_level = "basic"
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
                    "stem": "AI 自测：阅读理解",
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

    questions = PaperGenService().generate_for_self_test(
        db_session,
        org_id=org.id,
        student_user_id=student.id,
        subject_code="english",
        question_count=1,
    )

    assert len(questions) == 1
    prompt = captured["prompt"].lower()
    assert "cet" not in prompt
    assert "四六级" not in captured["prompt"]
    assert "math_mastery" not in prompt
    assert "数学基础" not in captured["prompt"]
    assert "english_1" in captured["prompt"]
