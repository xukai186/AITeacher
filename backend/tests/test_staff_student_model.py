import pytest
from sqlalchemy.exc import IntegrityError

from app.models import StaffStudent, UserRole
from tests.factories import make_org, make_user


def test_unique_staff_student_pair(db_session):
    org = make_org(db_session)
    staff = make_user(db_session, org, role=UserRole.org_staff, email="t@demo.example")
    student = make_user(db_session, org, role=UserRole.student, email="s@demo.example")
    db_session.add(StaffStudent(staff_user_id=staff.id, student_user_id=student.id))
    db_session.flush()
    with pytest.raises(IntegrityError):
        db_session.add(StaffStudent(staff_user_id=staff.id, student_user_id=student.id))
        db_session.flush()
