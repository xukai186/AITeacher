from app.auth.security import hash_password
from app.models import UserRole
from tests.factories import make_org, make_user


def _seed_admin_and_staff(db):
    org = make_org(db)
    make_user(
        db,
        org,
        role=UserRole.org_admin,
        email="a@demo.example",
        password_hash=hash_password("pw1234"),
    )
    staff = make_user(
        db,
        org,
        role=UserRole.org_staff,
        email="t@demo.example",
        password_hash=hash_password("pw1234"),
        name="Teacher One",
    )
    db.commit()
    return staff


def _token(client, email="a@demo.example"):
    return client.post(
        "/auth/login", json={"email": email, "password": "pw1234"}
    ).json()["access_token"]


def _create_student(client, token, email="s@demo.example"):
    return client.post(
        "/admin/students",
        json={"email": email, "name": "S", "password": "pw1234", "exam_year": 2027},
        headers={"Authorization": f"Bearer {token}"},
    ).json()["id"]


def test_admin_assigns_staff_to_student(client, db_session):
    staff = _seed_admin_and_staff(db_session)
    token = _token(client)
    student_id = _create_student(client, token)
    resp = client.post(
        f"/admin/students/{student_id}/staff",
        json={"staff_user_id": str(staff.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert str(staff.id) in body["staff_user_ids"]


def test_admin_unassigns_staff(client, db_session):
    staff = _seed_admin_and_staff(db_session)
    token = _token(client)
    student_id = _create_student(client, token)
    client.post(
        f"/admin/students/{student_id}/staff",
        json={"staff_user_id": str(staff.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = client.delete(
        f"/admin/students/{student_id}/staff/{staff.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["staff_user_ids"] == []


def test_assign_duplicate_is_idempotent(client, db_session):
    staff = _seed_admin_and_staff(db_session)
    token = _token(client)
    student_id = _create_student(client, token)
    for _ in range(2):
        resp = client.post(
            f"/admin/students/{student_id}/staff",
            json={"staff_user_id": str(staff.id)},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
    assert resp.json()["staff_user_ids"].count(str(staff.id)) == 1
