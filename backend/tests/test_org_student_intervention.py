from datetime import date, timedelta

from sqlalchemy import select

from app.auth.security import hash_password
from app.models import (
    AuditLog,
    MasterPlan,
    MasterPlanVersion,
    StaffStudent,
    StudentProfile,
    StudentSubject,
    UserRole,
)
from app.services.planning import PlanningService
from app.services.self_test import SelfTestService
from tests.factories import make_org, make_user


def _login(client, email, password):
    return client.post("/auth/login", json={"email": email, "password": password}).json()[
        "access_token"
    ]


def _seed_student_with_plan(db):
    org = make_org(db)
    admin = make_user(
        db, org, role=UserRole.org_admin, email="admin@demo.example", password_hash=hash_password("pw")
    )
    staff = make_user(
        db, org, role=UserRole.org_staff, email="staff@demo.example", password_hash=hash_password("pw")
    )
    student = make_user(
        db, org, role=UserRole.student, email="stu@demo.example", password_hash=hash_password("pw")
    )
    db.add(StudentProfile(user_id=student.id, exam_year=2027))
    db.add(StudentSubject(student_user_id=student.id, subject_code="english"))
    db.add(StaffStudent(staff_user_id=staff.id, student_user_id=student.id))
    db.commit()
    PlanningService().create_initial_plans(db, student_user_id=student.id)
    db.commit()
    return org, admin, staff, student


def test_admin_overview_and_master_budget_patch(client, db_session):
    _, admin, _, student = _seed_student_with_plan(db_session)
    token = _login(client, "admin@demo.example", "pw")
    headers = {"Authorization": f"Bearer {token}"}

    overview = client.get(f"/org/students/{student.id}/overview", headers=headers)
    assert overview.status_code == 200
    body = overview.json()
    assert body["student_id"] == str(student.id)
    assert "english" in body["subject_codes"]

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    patch = client.patch(
        f"/org/students/{student.id}/plans/master",
        headers=headers,
        json={"daily_time_budget_json": [{"date": tomorrow, "minutes": 120}]},
    )
    assert patch.status_code == 200
    assert patch.json()["source"] == "admin"

    plan = db_session.execute(
        select(MasterPlan).where(MasterPlan.student_user_id == student.id)
    ).scalar_one()
    ver = db_session.get(MasterPlanVersion, plan.current_version_id)
    assert ver.source == "admin"
    assert ver.daily_time_budget_json[0]["minutes"] == 120

    audit = db_session.execute(
        select(AuditLog).where(AuditLog.action == "plan.master_budget_update")
    ).scalar_one()
    assert audit.actor_user_id == admin.id


def test_staff_cannot_access_unassigned_student(client, db_session):
    org = make_org(db_session)
    make_user(
        db_session,
        org,
        role=UserRole.org_staff,
        email="staff@demo.example",
        password_hash=hash_password("pw"),
    )
    other = make_user(
        db_session,
        org,
        role=UserRole.student,
        email="other@demo.example",
        password_hash=hash_password("pw"),
    )
    db_session.commit()
    token = _login(client, "staff@demo.example", "pw")
    resp = client.get(
        f"/org/students/{other.id}/overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_lock_and_replace_paper(client, db_session):
    _, admin, _, student = _seed_student_with_plan(db_session)
    paper = SelfTestService.generate(db_session, student.id, "english")
    db_session.commit()

    token = _login(client, "admin@demo.example", "pw")
    headers = {"Authorization": f"Bearer {token}"}

    lock = client.post(
        f"/org/students/{student.id}/papers/{paper.id}/lock",
        headers=headers,
    )
    assert lock.status_code == 200
    assert lock.json()["status"] == "locked"

    gen_blocked = client.post(
        "/student/self-tests/generate",
        json={"subject_code": "english"},
        headers={"Authorization": f"Bearer {_login(client, 'stu@demo.example', 'pw')}"},
    )
    assert gen_blocked.status_code == 400

    replace = client.post(
        f"/org/students/{student.id}/papers/{paper.id}/replace",
        headers=headers,
    )
    assert replace.status_code == 200
    assert replace.json()["replaced_by_paper_id"]

    db_session.refresh(paper)
    assert paper.status == "replaced"
