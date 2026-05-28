import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Package, StudentProfile, StudentSubject, UserRole
from tests.factories import make_org, make_user


def test_create_package_and_student_profile(db_session):
    org = make_org(db_session)
    student = make_user(db_session, org, role=UserRole.student, email="s@demo.example")
    pkg = Package(org_id=org.id, name="Standard", subject_codes=["politics", "english"])
    db_session.add(pkg)
    db_session.flush()
    profile = StudentProfile(user_id=student.id, exam_year=2027, package_id=pkg.id)
    db_session.add(profile)
    db_session.flush()
    assert profile.package_id == pkg.id


def test_student_subject_unique_per_student(db_session):
    org = make_org(db_session)
    student = make_user(db_session, org, role=UserRole.student, email="s2@demo.example")
    db_session.add(StudentSubject(student_user_id=student.id, subject_code="math"))
    db_session.flush()
    with pytest.raises(IntegrityError):
        db_session.add(StudentSubject(student_user_id=student.id, subject_code="math"))
        db_session.flush()
