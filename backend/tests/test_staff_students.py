from app.auth.security import hash_password
from app.models import StaffStudent, StudentProfile, UserRole
from tests.factories import make_org, make_user


def _seed(db):
    org = make_org(db)
    staff = make_user(
        db,
        org,
        role=UserRole.org_staff,
        email="t@demo.example",
        password_hash=hash_password("pw1234"),
        name="Teacher",
    )
    other_staff = make_user(
        db,
        org,
        role=UserRole.org_staff,
        email="t2@demo.example",
        password_hash=hash_password("pw1234"),
    )
    mine = make_user(db, org, role=UserRole.student, email="mine@demo.example", name="Mine")
    theirs = make_user(db, org, role=UserRole.student, email="theirs@demo.example", name="Theirs")
    for s in (mine, theirs):
        db.add(StudentProfile(user_id=s.id, exam_year=2027))
    db.add(StaffStudent(staff_user_id=staff.id, student_user_id=mine.id))
    db.add(StaffStudent(staff_user_id=other_staff.id, student_user_id=theirs.id))
    db.commit()


def _token(client, email="t@demo.example"):
    return client.post(
        "/auth/login", json={"email": email, "password": "pw1234"}
    ).json()["access_token"]


def test_staff_sees_only_assigned_students(client, db_session):
    _seed(db_session)
    token = _token(client)
    resp = client.get("/staff/students", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    emails = {row["email"] for row in resp.json()}
    assert emails == {"mine@demo.example"}


def test_admin_cannot_use_staff_route(client, db_session):
    _seed(db_session)
    org = make_org(db_session, name="X")
    make_user(
        db_session,
        org,
        role=UserRole.org_admin,
        email="a@demo.example",
        password_hash=hash_password("pw1234"),
    )
    db_session.commit()
    token = _token(client, email="a@demo.example")
    resp = client.get("/staff/students", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
