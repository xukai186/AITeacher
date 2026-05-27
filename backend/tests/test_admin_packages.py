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


def _token(client):
    return client.post(
        "/auth/login", json={"email": "a@demo.example", "password": "pw1234"}
    ).json()["access_token"]


def _create_student(client, token, email="s@demo.example"):
    resp = client.post(
        "/admin/students",
        json={"email": email, "name": "S", "password": "pw1234", "exam_year": 2027},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def test_admin_create_and_list_package(client, db_session):
    _seed_admin(db_session)
    token = _token(client)
    resp = client.post(
        "/admin/packages",
        json={"name": "Standard", "subject_codes": ["politics", "english", "math"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    pkg = resp.json()
    assert pkg["subject_codes"] == ["politics", "english", "math"]

    resp = client.get("/admin/packages", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert any(p["name"] == "Standard" for p in resp.json())


def test_assign_package_creates_subjects(client, db_session):
    _seed_admin(db_session)
    token = _token(client)
    pkg = client.post(
        "/admin/packages",
        json={"name": "Std", "subject_codes": ["english", "math"]},
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    student_id = _create_student(client, token)
    resp = client.post(
        f"/admin/students/{student_id}/package",
        json={"package_id": pkg["id"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert set(resp.json()["subject_codes"]) == {"english", "math"}

    list_resp = client.get("/admin/students", headers={"Authorization": f"Bearer {token}"})
    matching = next(s for s in list_resp.json() if s["id"] == student_id)
    assert matching["package_id"] == pkg["id"]


def test_assign_package_idempotent_for_subjects(client, db_session):
    _seed_admin(db_session)
    token = _token(client)
    pkg = client.post(
        "/admin/packages",
        json={"name": "Std", "subject_codes": ["english"]},
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    student_id = _create_student(client, token)
    client.post(
        f"/admin/students/{student_id}/package",
        json={"package_id": pkg["id"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = client.post(
        f"/admin/students/{student_id}/package",
        json={"package_id": pkg["id"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["subject_codes"] == ["english"]
