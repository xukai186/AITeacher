from fastapi import APIRouter, Depends

from app.auth.deps import get_current_user
from app.models.user import User
from app.schemas.user import UserOut

router = APIRouter(tags=["me"])


@router.get("/me", response_model=UserOut)
def me(current: User = Depends(get_current_user)) -> User:
    return current
