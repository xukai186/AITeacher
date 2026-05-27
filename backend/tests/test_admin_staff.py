from app.auth.security import hash_password
from app.models import UserRole
from tests.factories import make_org, make_user


def _seed_admin(db):
    org = make_org(db)
    make_user(
        db,
        org,
        role=UserRole.org_admin,
        email="a@demo.example",
        password_hash=hash_password("pw1234"),
    )
    db.commit()


def _login(client, email="a@demo.example", password="pw1234"):
    return client.post("/auth/login", json={"email": email, "password": password}).json()[
        "access_token"
    ]


def test_admin_creates_staff(client, db_session):
    _seed_admin(db_session)
    token = _login(client)
    resp = client.post(
        "/admin/staff",
        json={"email": "t@demo.example", "name": "Teacher One", "password": "pw1234"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["email"] == "t@demo.example"


def test_admin_lists_staff(client, db_session):
    _seed_admin(db_session)
    token = _login(client)
    client.post(
        "/admin/staff",
        json={"email": "t@demo.example", "name": "Teacher One", "password": "pw1234"},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = client.get("/admin/staff", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    emails = {row["email"] for row in resp.json()}
    assert "t@demo.example" in emails


def test_staff_cannot_create_staff(client, db_session):
    org = make_org(db_session)
    make_user(
        db_session,
        org,
        role=UserRole.org_staff,
        email="t@demo.example",
        password_hash=hash_password("pw"),
    )
    db_session.commit()
    token = _login(client, "t@demo.example", "pw")
    resp = client.post(
        "/admin/staff",
        json={"email": "x@demo.example", "name": "X", "password": "pw1234"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
