from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.models.user import User, UserStatus
from app.schemas.auth import LoginRequest, LoginResponse

router = APIRouter(prefix="/auth", tags=["auth"])

_DUMMY_PASSWORD_HASH = hash_password("__not_a_real_password__")


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    candidate_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
    password_ok = verify_password(payload.password, candidate_hash)
    if user is None or user.status != UserStatus.active or not password_ok:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")

    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return LoginResponse(access_token=token)
