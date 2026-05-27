import pytest
from sqlalchemy.exc import IntegrityError

from app.models import UserRole
from tests.factories import make_org, make_user


def test_can_create_org_and_user(db_session):
    org = make_org(db_session)
    user = make_user(db_session, org, role=UserRole.org_admin, email="a@demo.example")
    assert user.org_id == org.id


def test_email_unique_per_org(db_session):
    org = make_org(db_session)
    make_user(db_session, org, role=UserRole.student, email="dup@demo.example")
    with pytest.raises(IntegrityError):
        make_user(db_session, org, role=UserRole.student, email="dup@demo.example")
        db_session.flush()
