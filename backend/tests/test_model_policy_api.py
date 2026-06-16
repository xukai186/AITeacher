from app.auth.security import hash_password
from app.models import ModelPolicy, UserRole
from tests.factories import make_org, make_user


def _seed_admin(db):
    org = make_org(db)
    make_user(
        db, org, role=UserRole.org_admin, email="admin@demo.example", password_hash=hash_password("pw")
    )
    db.commit()
    return org


def _token(client):
    return client.post("/auth/login", json={"email": "admin@demo.example", "password": "pw"}).json()[
        "access_token"
    ]


def test_admin_upserts_and_reads_model_policy(client, db_session):
    _seed_admin(db_session)
    token = _token(client)

    upsert = client.put(
        "/admin/model-policies/chat",
        json={"scene": "chat", "provider": "mock", "model": "mock-v1", "params": {"x": 1}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert upsert.status_code == 200
    assert upsert.json()["scene"] == "chat"
    assert upsert.json()["provider"] == "mock"

    get_resp = client.get(
        "/admin/model-policies",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp.status_code == 200
    assert any(p["scene"] == "chat" for p in get_resp.json())


def test_admin_upserts_grading_model_policy(client, db_session):
    _seed_admin(db_session)
    token = _token(client)

    upsert = client.put(
        "/admin/model-policies/grading",
        json={
            "scene": "grading",
            "provider": "openai_compat",
            "model": "qwen-plus",
            "params": {"base_url": "https://example.invalid/v1", "api_key": "k"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert upsert.status_code == 200
    assert upsert.json()["scene"] == "grading"
    assert upsert.json()["model"] == "qwen-plus"

