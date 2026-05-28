from app.auth.security import hash_password
from app.models import UserRole
from tests.factories import make_org, make_user


def _login(client, email, password):
    return client.post("/auth/login", json={"email": email, "password": password}).json()[
        "access_token"
    ]


def _seed_admin(db, email="admin@demo.example", password="admin123"):
    org = make_org(db)
    make_user(db, org, role=UserRole.org_admin, email=email, password_hash=hash_password(password))
    db.commit()
    return org


def test_admin_creates_student(client, db_session):
    _seed_admin(db_session)
    token = _login(client, "admin@demo.example", "admin123")
    resp = client.post(
        "/admin/students",
        json={
            "email": "stu@demo.example",
            "name": "Stu One",
            "password": "stu1234",
            "exam_year": 2027,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "stu@demo.example"
    assert body["exam_year"] == 2027


def test_admin_lists_students_in_own_org(client, db_session):
    org = _seed_admin(db_session)
    other_org = make_org(db_session, name="Other")
    make_user(db_session, other_org, role=UserRole.student, email="x@demo.example")
    db_session.commit()
    token = _login(client, "admin@demo.example", "admin123")
    client.post(
        "/admin/students",
        json={"email": "a@demo.example", "name": "A", "password": "pw1234", "exam_year": 2027},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = client.get("/admin/students", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    emails = {row["email"] for row in resp.json()}
    assert emails == {"a@demo.example"}


def test_student_cannot_list_students(client, db_session):
    org = make_org(db_session)
    make_user(
        db_session,
        org,
        role=UserRole.student,
        email="s@demo.example",
        password_hash=hash_password("pw"),
    )
    db_session.commit()
    token = _login(client, "s@demo.example", "pw")
    resp = client.get("/admin/students", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
