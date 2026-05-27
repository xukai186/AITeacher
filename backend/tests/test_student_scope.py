import uuid

import pytest
from fastapi import HTTPException

from app.auth.permissions import assert_can_access_student
from app.models import StaffStudent, UserRole
from tests.factories import make_org, make_user


def test_admin_can_access_any_student_in_same_org(db_session):
    org = make_org(db_session)
    admin = make_user(db_session, org, role=UserRole.org_admin, email="a@demo.example")
    student = make_user(db_session, org, role=UserRole.student, email="s@demo.example")
    assert_can_access_student(db_session, admin, student.id)


def test_admin_cannot_access_student_in_other_org(db_session):
    org_a = make_org(db_session, name="A")
    org_b = make_org(db_session, name="B")
    admin = make_user(db_session, org_a, role=UserRole.org_admin, email="a@demo.example")
    student = make_user(db_session, org_b, role=UserRole.student, email="s@demo.example")
    with pytest.raises(HTTPException) as exc:
        assert_can_access_student(db_session, admin, student.id)
    assert exc.value.status_code == 403


def test_staff_can_access_assigned_student_only(db_session):
    org = make_org(db_session)
    staff = make_user(db_session, org, role=UserRole.org_staff, email="t@demo.example")
    own = make_user(db_session, org, role=UserRole.student, email="o@demo.example")
    other = make_user(db_session, org, role=UserRole.student, email="x@demo.example")
    db_session.add(StaffStudent(staff_user_id=staff.id, student_user_id=own.id))
    db_session.flush()
    assert_can_access_student(db_session, staff, own.id)
    with pytest.raises(HTTPException) as exc:
        assert_can_access_student(db_session, staff, other.id)
    assert exc.value.status_code == 403


def test_student_can_access_only_self(db_session):
    org = make_org(db_session)
    student = make_user(db_session, org, role=UserRole.student, email="self@demo.example")
    other = make_user(db_session, org, role=UserRole.student, email="other@demo.example")
    assert_can_access_student(db_session, student, student.id)
    with pytest.raises(HTTPException) as exc:
        assert_can_access_student(db_session, student, other.id)
    assert exc.value.status_code == 403


def test_missing_student_raises_404(db_session):
    org = make_org(db_session)
    admin = make_user(db_session, org, role=UserRole.org_admin, email="a@demo.example")
    with pytest.raises(HTTPException) as exc:
        assert_can_access_student(db_session, admin, uuid.uuid4())
    assert exc.value.status_code == 404
