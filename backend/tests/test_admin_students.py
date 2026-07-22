from datetime import datetime, timezone

from app.auth.security import hash_password
from app.models import StudentExamProfile, StudentProfile, UserRole
from app.seed_exam_majors import seed_exam_majors
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


def test_admin_list_includes_exam_profile_complete(client, db_session):
    seed_exam_majors(db_session)
    org = _seed_admin(db_session)
    complete = make_user(
        db_session, org, role=UserRole.student, email="complete@demo.example", name="Complete"
    )
    incomplete = make_user(
        db_session, org, role=UserRole.student, email="incomplete@demo.example", name="Incomplete"
    )
    for student in (complete, incomplete):
        db_session.add(StudentProfile(user_id=student.id, exam_year=2027))
    db_session.add(
        StudentExamProfile(
            user_id=complete.id,
            major_category_code="academic_master",
            major_code="cs_academic",
            subject_codes=["english", "math", "politics"],
            profile_completed_at=datetime.now(timezone.utc),
        )
    )
    db_session.add(
        StudentExamProfile(
            user_id=incomplete.id,
            major_category_code="academic_master",
            major_code="cs_academic",
            subject_codes=["english", "math", "politics"],
        )
    )
    db_session.commit()

    token = _login(client, "admin@demo.example", "admin123")
    resp = client.get("/admin/students", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    by_email = {row["email"]: row for row in resp.json()}
    assert by_email["complete@demo.example"]["exam_profile_complete"] is True
    assert by_email["incomplete@demo.example"]["exam_profile_complete"] is False


def test_admin_list_includes_staff_user_ids(client, db_session):
    from app.models import StaffStudent

    org = _seed_admin(db_session)
    staff = make_user(
        db_session,
        org,
        role=UserRole.org_staff,
        email="teacher@demo.example",
        password_hash=hash_password("pw"),
        name="Teacher",
    )
    student = make_user(
        db_session,
        org,
        role=UserRole.student,
        email="assigned@demo.example",
        name="Assigned",
    )
    db_session.add(StudentProfile(user_id=student.id, exam_year=2027))
    db_session.add(StaffStudent(staff_user_id=staff.id, student_user_id=student.id))
    db_session.commit()

    token = _login(client, "admin@demo.example", "admin123")
    resp = client.get("/admin/students", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    by_email = {row["email"]: row for row in resp.json()}
    assert by_email["assigned@demo.example"]["staff_user_ids"] == [str(staff.id)]
