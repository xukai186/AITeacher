from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models import Organization, User, UserRole, UserStatus


def make_org(db: Session, name: str = "Demo Org") -> Organization:
    org = Organization(name=name)
    db.add(org)
    db.flush()
    return org


def make_user(
    db: Session,
    org: Organization,
    role: UserRole,
    email: str | None = None,
    password_hash: str = "x",
    name: str = "Test User",
) -> User:
    user = User(
        org_id=org.id,
        email=email or f"{role.value}-{uuid.uuid4().hex[:8]}@demo.example",
        password_hash=password_hash,
        role=role,
        status=UserStatus.active,
        name=name,
    )
    db.add(user)
    db.flush()
    return user
