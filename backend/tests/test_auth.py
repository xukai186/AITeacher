from app.auth.security import hash_password
from app.models import UserRole
from tests.factories import make_org, make_user


def _seed_admin(db, email="admin@demo.example", password="admin123"):
    org = make_org(db)
    user = make_user(
        db, org, role=UserRole.org_admin, email=email, password_hash=hash_password(password)
    )
    db.commit()
    return user


def test_login_success_returns_jwt(client, db_session):
    _seed_admin(db_session)
    resp = client.post("/auth/login", json={"email": "admin@demo.example", "password": "admin123"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_wrong_password_rejected(client, db_session):
    _seed_admin(db_session)
    resp = client.post("/auth/login", json={"email": "admin@demo.example", "password": "nope"})
    assert resp.status_code == 401


def test_me_requires_auth(client):
    resp = client.get("/me")
    assert resp.status_code == 401


def test_me_returns_current_user(client, db_session):
    user = _seed_admin(db_session)
    token = client.post(
        "/auth/login", json={"email": "admin@demo.example", "password": "admin123"}
    ).json()["access_token"]
    resp = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "admin@demo.example"
    assert body["role"] == "org_admin"
    assert body["id"] == str(user.id)
