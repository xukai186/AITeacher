from __future__ import annotations

from app.auth.security import hash_password
from app.models import StudentExamProfile, UserRole
from app.seed_exam_majors import seed_exam_majors
from app.services.planning import PlanningService
from tests.factories import make_org, make_user


def _login(client, email: str, password: str) -> str:
    return client.post("/auth/login", json={"email": email, "password": password}).json()[
        "access_token"
    ]


def _seed_admin(db, email: str = "admin@demo.example", password: str = "admin123"):
    org = make_org(db)
    admin = make_user(
        db,
        org,
        role=UserRole.org_admin,
        email=email,
        password_hash=hash_password(password),
        name="Admin",
    )
    db.commit()
    return org, admin


def test_list_majors_by_category(client, db_session):
    seed_exam_majors(db_session)
    org = make_org(db_session)
    student = make_user(
        db_session,
        org,
        role=UserRole.student,
        email="catalog-student@demo.example",
        password_hash=hash_password("stu123"),
    )
    db_session.commit()

    token = _login(client, student.email, "stu123")

    resp = client.get("/exam-majors?category=academic_master", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    majors = resp.json()
    assert majors
    assert all(row["category_code"] == "academic_master" for row in majors)

    cat_resp = client.get("/exam-majors/categories", headers={"Authorization": f"Bearer {token}"})
    assert cat_resp.status_code == 200
    categories = cat_resp.json()
    assert categories == sorted(categories, key=lambda item: item["sort_order"])


def test_admin_put_and_get_exam_profile(client, db_session):
    seed_exam_majors(db_session)
    org, _admin = _seed_admin(db_session)
    student = make_user(db_session, org, role=UserRole.student, email="profile-student@demo.example")
    db_session.commit()
    token = _login(client, "admin@demo.example", "admin123")

    put_resp = client.put(
        f"/admin/students/{student.id}/exam-profile",
        json={
            "major_category_code": "academic_master",
            "major_code": "cs_academic",
            "cet_status": "cet4",
            "cet_score": 460,
            "math_mastery_level": "basic",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert put_resp.status_code == 200
    put_body = put_resp.json()
    assert put_body["major_code"] == "cs_academic"
    assert put_body["subject_codes"] == ["english", "math", "politics"]
    assert put_body["english_track"] is None
    assert put_body["math_track"] is None
    assert put_body["effective_english_track"] == "english_1"
    assert put_body["effective_math_track"] == "math_1"
    assert put_body["is_complete"] is False

    get_resp = client.get(
        f"/admin/students/{student.id}/exam-profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp.status_code == 200
    get_body = get_resp.json()
    assert get_body["major_name"] == "计算机科学与技术"
    assert get_body["cet_status"] == "cet4"


def test_staff_cannot_edit_unassigned_student(client, db_session):
    seed_exam_majors(db_session)
    org = make_org(db_session)
    staff = make_user(
        db_session,
        org,
        role=UserRole.org_staff,
        email="staff@demo.example",
        password_hash=hash_password("staff123"),
    )
    student = make_user(db_session, org, role=UserRole.student, email="student@demo.example")
    db_session.commit()

    token = _login(client, staff.email, "staff123")
    resp = client.put(
        f"/staff/students/{student.id}/exam-profile",
        json={"major_category_code": "academic_master", "major_code": "cs_academic"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_confirm_does_not_create_initial_plans(client, db_session, monkeypatch):
    seed_exam_majors(db_session)
    org, _admin = _seed_admin(db_session)
    student = make_user(db_session, org, role=UserRole.student, email="confirm-student@demo.example")
    db_session.commit()

    token = _login(client, "admin@demo.example", "admin123")
    client.put(
        f"/admin/students/{student.id}/exam-profile",
        json={
            "major_category_code": "academic_master",
            "major_code": "cs_academic",
            "subject_codes": ["english", "politics"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    calls: list = []

    def _fake_create_initial_plans(self, db, student_user_id):
        calls.append(student_user_id)

    monkeypatch.setattr(PlanningService, "create_initial_plans", _fake_create_initial_plans)

    resp = client.post(
        f"/admin/students/{student.id}/exam-profile/confirm",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_complete"] is True
    assert body["profile_completed_at"] is not None
    assert calls == []


def test_student_can_read_own_profile(client, db_session):
    seed_exam_majors(db_session)
    org = make_org(db_session)
    student = make_user(
        db_session,
        org,
        role=UserRole.student,
        email="self-profile@demo.example",
        password_hash=hash_password("stu123"),
    )
    db_session.add(
        StudentExamProfile(
            user_id=student.id,
            major_category_code="academic_master",
            major_code="cs_academic",
            subject_codes=["english", "math", "politics"],
        )
    )
    db_session.commit()

    token = _login(client, student.email, "stu123")
    resp = client.get("/student/exam-profile", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["major_code"] == "cs_academic"
    assert body["major_name"] == "计算机科学与技术"


def test_student_cannot_put_profile(client, db_session):
    seed_exam_majors(db_session)
    org = make_org(db_session)
    student = make_user(
        db_session,
        org,
        role=UserRole.student,
        email="readonly@demo.example",
        password_hash=hash_password("stu123"),
    )
    db_session.commit()

    token = _login(client, student.email, "stu123")
    resp = client.put(
        f"/admin/students/{student.id}/exam-profile",
        json={"major_category_code": "academic_master", "major_code": "cs_academic"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_put_cet_only_triggers_light_revise(client, db_session, monkeypatch):
    from datetime import datetime, timezone

    seed_exam_majors(db_session)
    org, _admin = _seed_admin(db_session)
    student = make_user(db_session, org, role=UserRole.student, email="cet-only@demo.example")
    db_session.add(
        StudentExamProfile(
            user_id=student.id,
            major_category_code="academic_master",
            major_code="cs_academic",
            subject_codes=["english", "math", "politics"],
            cet_status="cet4",
            profile_completed_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()
    token = _login(client, "admin@demo.example", "admin123")

    called: list = []

    def _fake_light(self, db, student_user_id):
        called.append(student_user_id)

    monkeypatch.setattr(PlanningService, "light_revise_from_profile", _fake_light)

    resp = client.put(
        f"/admin/students/{student.id}/exam-profile",
        json={
            "major_category_code": "academic_master",
            "major_code": "cs_academic",
            "cet_status": "not_taken",
            "math_mastery_level": "basic",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert called == [student.id]


def test_put_track_change_does_not_light_revise(client, db_session, monkeypatch):
    from datetime import datetime, timezone

    seed_exam_majors(db_session)
    org, _admin = _seed_admin(db_session)
    student = make_user(db_session, org, role=UserRole.student, email="track-change@demo.example")
    db_session.add(
        StudentExamProfile(
            user_id=student.id,
            major_category_code="academic_master",
            major_code="cs_academic",
            subject_codes=["english", "math", "politics"],
            english_track="english_1",
            profile_completed_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()
    token = _login(client, "admin@demo.example", "admin123")

    called: list = []

    def _fake_light(self, db, student_user_id):
        called.append(student_user_id)

    monkeypatch.setattr(PlanningService, "light_revise_from_profile", _fake_light)

    resp = client.put(
        f"/admin/students/{student.id}/exam-profile",
        json={
            "major_category_code": "academic_master",
            "major_code": "cs_academic",
            "english_track": "english_2",
            "math_mastery_level": "basic",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert called == []
