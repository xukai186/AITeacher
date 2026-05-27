from app.auth.security import hash_password
from app.models import UserRole
from tests.factories import make_org, make_user


def _login(client, db, role: UserRole, email: str):
    org = make_org(db, name=f"Org-{role.value}")
    make_user(db, org, role=role, email=email, password_hash=hash_password("pw"))
    db.commit()
    return client.post("/auth/login", json={"email": email, "password": "pw"}).json()[
        "access_token"
    ]


def test_admin_only_route_rejects_student(client, db_session):
    token = _login(client, db_session, UserRole.student, "s@demo.example")
    resp = client.get("/admin/ping", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_admin_only_route_allows_admin(client, db_session):
    token = _login(client, db_session, UserRole.org_admin, "a@demo.example")
    resp = client.get("/admin/ping", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == {"pong": "admin"}
