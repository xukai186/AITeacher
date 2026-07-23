from sqlalchemy import select

from app.auth.security import hash_password
from app.models import (
    DailyTask,
    ModelPolicy,
    PlanReviewJob,
    StudentProfile,
    StudentSubject,
    SubjectPlanVersion,
    UserRole,
)
from app.services.chat_tool_executor import ChatToolExecutor
from app.services.chat_tool_loop import ChatToolLoop
from app.services.model_gateway import ModelGateway
from app.services.paper_gen_jobs import PaperGenJobRunner
from app.services.placement import PlacementService
from app.services.planning import PlanningService
from tests.exam_profile_helpers import add_complete_exam_profile
from tests.factories import make_org, make_user


def _seed_student(db):
    org = make_org(db)
    student = make_user(
        db,
        org,
        role=UserRole.student,
        email="chat-ext@demo.example",
        password_hash=hash_password("pw"),
    )
    db.add(StudentProfile(user_id=student.id, exam_year=2027))
    add_complete_exam_profile(db, student.id)
    db.add(StudentSubject(student_user_id=student.id, subject_code="english", enabled=True))
    db.add(ModelPolicy(org_id=org.id, scene="chat", provider="mock", model="mock-v1", params={}))
    db.add(ModelPolicy(org_id=org.id, scene="paper_gen", provider="mock", model="mock-v1", params={}))
    db.commit()
    PlanningService().create_initial_plans(db, student_user_id=student.id)
    db.commit()
    return student


def test_explain_question_for_placement(db_session):
    student = _seed_student(db_session)
    out = PlacementService.start(db_session, student.id, subject_code="english")
    if out.gen_job_id is not None:
        PaperGenJobRunner().run_pending(db_session, limit=1, job_id=out.gen_job_id)
        db_session.commit()

    listed = ChatToolExecutor().execute(
        db_session,
        tool_name="list_papers",
        arguments={"limit": 1},
        student_user_id=student.id,
        default_subject_code="english",
        agent_type="subject",
    )
    paper_id = listed["placement_papers"][0]["paper_id"]

    explained = ChatToolExecutor().execute(
        db_session,
        tool_name="explain_question",
        arguments={"paper_type": "placement", "paper_id": paper_id, "question_seq": 1},
        student_user_id=student.id,
        default_subject_code="english",
        agent_type="subject",
    )
    assert explained["paper_type"] == "placement"
    assert explained["question_seq"] == 1
    assert explained["stem"]
    assert explained["explanation_hint"]


def test_propose_subject_plan_and_request_adjustment(db_session):
    student = _seed_student(db_session)
    executor = ChatToolExecutor()

    proposed = executor.execute(
        db_session,
        tool_name="propose_subject_plan",
        arguments={
            "phases": [{"title": "强化阅读", "days": 5, "notes": "每天精读一篇"}],
        },
        student_user_id=student.id,
        default_subject_code="english",
        agent_type="subject",
    )
    assert proposed["ok"] is True
    assert proposed["version"] >= 2

    versions = db_session.execute(select(SubjectPlanVersion)).scalars().all()
    assert len(versions) >= 2

    requested = executor.execute(
        db_session,
        tool_name="request_plan_adjustment",
        arguments={"reason": "最近任务太多"},
        student_user_id=student.id,
        default_subject_code="english",
        agent_type="subject",
    )
    assert requested["ok"] is True
    job = db_session.execute(
        select(PlanReviewJob).where(PlanReviewJob.student_user_id == student.id)
    ).scalar_one()
    assert job.trigger == "chat_request"


def test_planner_weekly_calendar_and_propose_master_plan(db_session):
    student = _seed_student(db_session)
    db_session.add(
        DailyTask(
            student_user_id=student.id,
            date=__import__("datetime").date.today(),
            subject_code="english",
            type="study",
            status="pending",
            est_minutes=30,
            title="英语学习",
        )
    )
    db_session.commit()

    executor = ChatToolExecutor()
    calendar = executor.execute(
        db_session,
        tool_name="get_weekly_calendar",
        arguments={},
        student_user_id=student.id,
        default_subject_code=None,
        agent_type="planner",
    )
    assert len(calendar["days"]) == 7
    assert calendar["days"][0]["task_count"] >= 1

    proposed = executor.execute(
        db_session,
        tool_name="propose_master_plan",
        arguments={"daily_minutes": 60},
        student_user_id=student.id,
        default_subject_code=None,
        agent_type="planner",
    )
    assert proposed["ok"] is True


def test_mock_chat_triggers_explain_question(db_session):
    student = _seed_student(db_session)
    turn = ChatToolLoop(model_gateway=ModelGateway()).run(
        db_session,
        student_user_id=student.id,
        agent_type="subject",
        subject_code="english",
        provider="mock",
        model="mock-v1",
        params={},
        history_messages=[],
        user_message="请讲解第1题",
    )
    assert "explain_question" in turn.tools_used


def test_explain_wrong_book_item_matches_list_index(db_session):
    from app.models import WrongBookItem
    from datetime import datetime, timedelta, timezone

    student = _seed_student(db_session)
    now = datetime.now(timezone.utc)
    older = WrongBookItem(
        student_user_id=student.id,
        subject_code="english",
        source_type="placement",
        source_id=None,
        question_snapshot_json={"stem": "OLDER_STEM", "seq": 9, "q_type": "single_choice", "choices": []},
        answer_snapshot_json={"content": "A"},
        correct_snapshot_json={"answer_key": "B"},
        status="active",
    )
    newer = WrongBookItem(
        student_user_id=student.id,
        subject_code="english",
        source_type="self_test",
        source_id=None,
        question_snapshot_json={"stem": "NEWER_STEM", "seq": 2, "q_type": "single_choice", "choices": []},
        answer_snapshot_json={"content": "C"},
        correct_snapshot_json={"answer_key": "D"},
        status="active",
    )
    db_session.add(older)
    db_session.add(newer)
    db_session.flush()
    older.created_at = now - timedelta(hours=2)
    newer.created_at = now - timedelta(hours=1)
    db_session.commit()

    executor = ChatToolExecutor()
    listed = executor.execute(
        db_session,
        tool_name="list_wrong_book",
        arguments={},
        student_user_id=student.id,
        default_subject_code="english",
        agent_type="subject",
    )
    assert listed["count"] == 2
    assert listed["items"][0]["list_index"] == 1
    assert listed["items"][0]["stem"] == "NEWER_STEM"
    assert listed["items"][1]["list_index"] == 2
    assert listed["items"][1]["stem"] == "OLDER_STEM"

    # list_index=1 must be newer item — NOT paper seq 1
    explained = executor.execute(
        db_session,
        tool_name="explain_wrong_book_item",
        arguments={"list_index": 1},
        student_user_id=student.id,
        default_subject_code="english",
        agent_type="subject",
    )
    assert explained["stem"] == "NEWER_STEM"
    assert explained["list_index"] == 1
    assert explained["source_question_seq"] == 2
    assert "错题本" in explained["explanation_hint"]

    explained2 = executor.execute(
        db_session,
        tool_name="explain_wrong_book_item",
        arguments={"list_index": 2},
        student_user_id=student.id,
        default_subject_code="english",
        agent_type="subject",
    )
    assert explained2["stem"] == "OLDER_STEM"
    assert explained2["source_question_seq"] == 9


def test_mock_chat_wrong_book_uses_explain_wrong_book_item(db_session):
    from app.models import WrongBookItem

    student = _seed_student(db_session)
    db_session.add(
        WrongBookItem(
            student_user_id=student.id,
            subject_code="english",
            source_type="placement",
            question_snapshot_json={"stem": "WB_STEM", "seq": 5, "q_type": "single_choice"},
            answer_snapshot_json={"content": "A"},
            correct_snapshot_json={"answer_key": "B"},
            status="active",
        )
    )
    db_session.commit()

    turn = ChatToolLoop(model_gateway=ModelGateway()).run(
        db_session,
        student_user_id=student.id,
        agent_type="subject",
        subject_code="english",
        provider="mock",
        model="mock-v1",
        params={},
        history_messages=[],
        user_message="请分析错题本第1题",
    )
    assert "explain_wrong_book_item" in turn.tools_used
    assert "explain_question" not in turn.tools_used
    assert "WB_STEM" in turn.assistant_message or "错题本第 1 题" in turn.assistant_message


def test_mock_chat_wrong_book_explain_uses_item_id(db_session):
    from app.models import WrongBookItem

    student = _seed_student(db_session)
    older = WrongBookItem(
        student_user_id=student.id,
        subject_code="english",
        source_type="placement",
        question_snapshot_json={"stem": "OLDER_STEM", "seq": 1, "q_type": "single_choice"},
        answer_snapshot_json={"content": "A"},
        correct_snapshot_json={"answer_key": "B"},
        status="active",
    )
    newer = WrongBookItem(
        student_user_id=student.id,
        subject_code="english",
        source_type="self_test",
        question_snapshot_json={"stem": "NEWER_STEM", "seq": 2, "q_type": "single_choice"},
        answer_snapshot_json={"content": "C"},
        correct_snapshot_json={"answer_key": "D"},
        status="active",
    )
    db_session.add_all([older, newer])
    db_session.commit()
    db_session.refresh(older)

    # List order is created_at desc → newer is list_index 1. Point at older via item_id.
    turn = ChatToolLoop(model_gateway=ModelGateway()).run(
        db_session,
        student_user_id=student.id,
        agent_type="subject",
        subject_code="english",
        provider="mock",
        model="mock-v1",
        params={},
        history_messages=[],
        user_message=(
            f"请讲解错题本条目 item_id={older.id}（页面错题 2）。"
            "结合我的当时作答说明错因与正确思路。"
        ),
    )
    assert "explain_wrong_book_item" in turn.tools_used
    assert "explain_question" not in turn.tools_used
    assert "OLDER_STEM" in turn.assistant_message
    assert "NEWER_STEM" not in turn.assistant_message
