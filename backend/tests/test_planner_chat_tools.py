from app.auth.security import hash_password
from app.models import ModelPolicy, StudentProfile, StudentSubject, UserRole
from app.services.chat_tool_loop import ChatToolLoop
from app.services.model_gateway import ModelGateway
from app.services.planning import PlanningService
from tests.factories import make_org, make_user


def _seed(db):
    org = make_org(db)
    student = make_user(
        db,
        org,
        role=UserRole.student,
        email="planner-chat@demo.example",
        password_hash=hash_password("pw"),
    )
    db.add(StudentProfile(user_id=student.id, exam_year=2027))
    db.add(StudentSubject(student_user_id=student.id, subject_code="english"))
    db.add(ModelPolicy(org_id=org.id, scene="chat", provider="mock", model="mock-v1", params={}))
    db.commit()
    PlanningService().create_initial_plans(db, student_user_id=student.id)
    db.commit()
    return student


def test_planner_chat_get_master_plan(db_session):
    student = _seed(db_session)
    turn = ChatToolLoop(model_gateway=ModelGateway()).run(
        db_session,
        student_user_id=student.id,
        agent_type="planner",
        subject_code=None,
        provider="mock",
        model="mock-v1",
        params={},
        history_messages=[],
        user_message="帮我看看总规划和时间预算",
    )
    assert "get_master_plan" in turn.tools_used
    assert "总规划" in turn.assistant_message or "预算" in turn.assistant_message


def test_planner_chat_trigger_plan_review(db_session):
    student = _seed(db_session)
    turn = ChatToolLoop(model_gateway=ModelGateway()).run(
        db_session,
        student_user_id=student.id,
        agent_type="planner",
        subject_code=None,
        provider="mock",
        model="mock-v1",
        params={},
        history_messages=[],
        user_message="请帮我安排明天的学习任务",
    )
    assert "trigger_plan_review" in turn.tools_used
    assert "已提交" in turn.assistant_message or "复审" in turn.assistant_message
