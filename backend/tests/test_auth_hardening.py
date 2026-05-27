from app.auth.security import create_access_token, hash_password
from app.models import UserRole
from tests.factories import make_org, make_user


def test_login_unknown_email_returns_401(client):
    resp = client.post(
        "/auth/login", json={"email": "ghost@demo.example", "password": "whatever"}
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid credentials"


def test_me_rejects_non_uuid_subject(client):
    token = create_access_token({"sub": "not-a-uuid", "role": "org_admin"})
    resp = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_me_rejects_unknown_user(client):
    token = create_access_token(
        {"sub": "00000000-0000-0000-0000-000000000000", "role": "org_admin"}
    )
    resp = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_inactive_user_cannot_authenticate(client, db_session):
    from app.models.user import UserStatus

    org = make_org(db_session)
    inactive = make_user(
        db_session,
        org,
        role=UserRole.org_admin,
        email="ghost-admin@demo.example",
        password_hash=hash_password("pw"),
    )
    inactive.status = UserStatus.inactive
    db_session.commit()

    resp = client.post(
        "/auth/login",
        json={"email": "ghost-admin@demo.example", "password": "pw"},
    )
    assert resp.status_code == 401
