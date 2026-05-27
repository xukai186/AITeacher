from sqlalchemy import select

from app.models import AuditLog, UserRole
from app.services.audit import record_audit
from tests.factories import make_org, make_user


def test_record_audit_persists_actor_and_payload(db_session):
    org = make_org(db_session)
    actor = make_user(db_session, org, role=UserRole.org_admin, email="a@demo.example")
    record_audit(
        db_session,
        actor=actor,
        action="student.assign_staff",
        target_type="student",
        target_id="abc-123",
        before=None,
        after={"staff_id": "staff-1"},
    )
    db_session.flush()
    row = db_session.execute(select(AuditLog)).scalar_one()
    assert row.action == "student.assign_staff"
    assert row.actor_user_id == actor.id
    assert row.actor_role == "org_admin"
    assert row.after == {"staff_id": "staff-1"}
    assert row.org_id == org.id
