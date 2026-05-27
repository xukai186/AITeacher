from collections.abc import Iterable

from fastapi import Depends, HTTPException, status

from app.auth.deps import get_current_user
from app.models.user import User, UserRole


def require_roles(*roles: UserRole):
    allowed: tuple[UserRole, ...] = tuple(roles)

    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient role")
        return user

    return _dep


def require_admin():
    return require_roles(UserRole.org_admin)


def require_staff_or_admin():
    return require_roles(UserRole.org_admin, UserRole.org_staff)


def require_any(roles: Iterable[UserRole]):
    return require_roles(*roles)
