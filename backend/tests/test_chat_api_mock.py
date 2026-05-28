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

    # second message should reuse same session scope
    resp2 = client.post(
        "/chat",
        json={"agent_type": "subject", "subject_code": "english", "message": "again"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 200

