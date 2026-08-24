from app.auth.security import hash_password
from app.models import ModelPolicy, UserRole
from tests.factories import make_org, make_user


def _seed_student_and_policy(db):
    org = make_org(db)
    admin = make_user(db, org, role=UserRole.org_admin, email="admin@demo.example", password_hash=hash_password("pw"))
    student = make_user(db, org, role=UserRole.student, email="student@demo.example", password_hash=hash_password("pw"))
    db.add(ModelPolicy(org_id=org.id, scene="chat", provider="mock", model="mock-v1", params={}))
    db.commit()
    return admin, student


def _token(client, email):
    return client.post("/auth/login", json={"email": email, "password": "pw"}).json()["access_token"]


def test_student_chat_creates_session_and_persists_messages(client, db_session):
    _, student = _seed_student_and_policy(db_session)
    token = _token(client, "student@demo.example")

    resp = client.post(
        "/chat",
        json={"agent_type": "subject", "subject_code": "english", "message": "hi"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"]
    assert "mock" in body["assistant_message"]
    assert body.get("tools_used") == []

    # second message should reuse same session scope
    resp2 = client.post(
        "/chat",
        json={"agent_type": "subject", "subject_code": "english", "message": "again"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 200


def test_student_can_load_chat_history(client, db_session):
    _seed_student_and_policy(db_session)
    token = _token(client, "student@demo.example")
    headers = {"Authorization": f"Bearer {token}"}

    empty = client.get(
        "/chat?agent_type=subject&subject_code=english",
        headers=headers,
    )
    assert empty.status_code == 200
    assert empty.json() == {"session_id": None, "messages": []}

    client.post(
        "/chat",
        json={"agent_type": "subject", "subject_code": "english", "message": "hi"},
        headers=headers,
    )
    client.post(
        "/chat",
        json={"agent_type": "subject", "subject_code": "english", "message": "again"},
        headers=headers,
    )

    history = client.get(
        "/chat?agent_type=subject&subject_code=english",
        headers=headers,
    )
    assert history.status_code == 200
    body = history.json()
    assert body["session_id"]
    roles = [row["role"] for row in body["messages"]]
    contents = [row["content"] for row in body["messages"]]
    assert roles == ["user", "assistant", "user", "assistant"]
    assert contents[0] == "hi"
    assert contents[2] == "again"
    assert all(not text.startswith("__TOOL_CALLS__:") for text in contents)


def test_subject_chat_triggers_tool_loop(client, db_session):
    _seed_student_and_policy(db_session)
    token = _token(client, "student@demo.example")

    resp = client.post(
        "/chat",
        json={
            "agent_type": "subject",
            "subject_code": "english",
            "message": "帮我看看学情和薄弱点",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "get_subject_context" in body.get("tools_used", [])
    assert body["assistant_message"]

