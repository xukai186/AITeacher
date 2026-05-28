from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog, User


def record_audit(
    db: Session,
    *,
    actor: User,
    action: str,
    target_type: str,
    target_id: str,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        org_id=actor.org_id,
        actor_user_id=actor.id,
        actor_role=actor.role.value,
        action=action,
        target_type=target_type,
        target_id=target_id,
        before=before,
        after=after,
    )
    db.add(entry)
    return entry
