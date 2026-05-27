from app.auth.security import hash_password
from app.models import StudentProfile, StudentSubject, UserRole
from tests.factories import make_org, make_user


def _seed(db):
    org = make_org(db)
    student = make_user(
        db,
        org,
        role=UserRole.student,
        email="s@demo.example",
        password_hash=hash_password("pw1234"),
        name="Stu",
    )
    db.add(StudentProfile(user_id=student.id, exam_year=2027))
    db.add(StudentSubject(student_user_id=student.id, subject_code="english"))
    db.add(StudentSubject(student_user_id=student.id, subject_code="math"))
    db.commit()
    return student


def test_student_sees_own_profile_and_subjects(client, db_session):
    _seed(db_session)
    token = client.post(
        "/auth/login", json={"email": "s@demo.example", "password": "pw1234"}
    ).json()["access_token"]
    resp = client.get("/student/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "s@demo.example"
    assert body["exam_year"] == 2027
    assert set(body["subject_codes"]) == {"english", "math"}


def test_non_student_role_rejected(client, db_session):
    org = make_org(db_session)
    make_user(
        db_session,
        org,
        role=UserRole.org_admin,
        email="a@demo.example",
        password_hash=hash_password("pw1234"),
    )
    db_session.commit()
    token = client.post(
        "/auth/login", json={"email": "a@demo.example", "password": "pw1234"}
    ).json()["access_token"]
    resp = client.get("/student/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
