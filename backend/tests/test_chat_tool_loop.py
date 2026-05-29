import json

from app.auth.security import hash_password
from app.models import ModelPolicy, StudentProfile, StudentSubject, UserRole
from app.services.chat_tool_loop import ChatToolLoop
from app.services.model_gateway import ModelGateway
from app.services.planning import PlanningService
from tests.factories import make_org, make_user


def _seed_student(db):
    org = make_org(db)
    student = make_user(
        db,
        org,
        role=UserRole.student,
        email="chat-tools@demo.example",
        password_hash=hash_password("pw"),
    )
    db.add(StudentProfile(user_id=student.id, exam_year=2027))
    db.add(StudentSubject(student_user_id=student.id, subject_code="english"))
    db.add(ModelPolicy(org_id=org.id, scene="chat", provider="mock", model="mock-v1", params={}))
    db.commit()
    PlanningService().create_initial_plans(db, student_user_id=student.id)
    db.commit()
    return student


def test_mock_chat_loop_calls_get_subject_context(db_session):
    student = _seed_student(db_session)
    loop = ChatToolLoop(model_gateway=ModelGateway())
    turn = loop.run(
        db_session,
        student_user_id=student.id,
        agent_type="subject",
        subject_code="english",
        provider="mock",
        model="mock-v1",
        params={},
        history_messages=[],
        user_message="帮我看看学情和薄弱点",
    )
    assert "get_subject_context" in turn.tools_used
    assert "学情" in turn.assistant_message or "薄弱" in turn.assistant_message


def test_mock_chat_loop_calls_generate_daily_tasks(db_session):
    student = _seed_student(db_session)
    loop = ChatToolLoop(model_gateway=ModelGateway())
    turn = loop.run(
        db_session,
        student_user_id=student.id,
        agent_type="subject",
        subject_code="english",
        provider="mock",
        model="mock-v1",
        params={},
        history_messages=[],
        user_message="请帮我生成明天的学习任务",
    )
    assert "generate_daily_tasks" in turn.tools_used
    assert "任务" in turn.assistant_message


def test_openai_compat_tool_loop_roundtrip():
    calls = {"n": 0}

    def handler(request):
        body = json.loads(request.content.decode())
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "tool_calls": [
                                    {
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {
                                            "name": "get_subject_context",
                                            "arguments": "{}",
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "学情已查询完毕。"}}]},
        )

    import httpx

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="https://example.invalid")
    gw = ModelGateway(http_client=client)

    completion = gw.complete(
        provider="openai_compat",
        model="gpt-test",
        scene="chat",
        messages=[{"role": "user", "content": "学情"}],
        tools=[
            {
                "type": "function",
                "function": {"name": "get_subject_context", "parameters": {"type": "object"}},
            }
        ],
        params={"base_url": "https://example.invalid", "api_key": "k"},
    )
    assert len(completion.tool_calls) == 1
    assert completion.tool_calls[0].name == "get_subject_context"
