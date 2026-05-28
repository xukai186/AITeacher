from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.permissions import require_roles
from app.database import get_db
from app.models import User, UserRole
from app.schemas.wrong_book import WrongBookItemOut
from app.services.wrong_book import WrongBookService

router = APIRouter(prefix="/student/wrong-book", tags=["student-wrong-book"])


@router.get("", response_model=list[WrongBookItemOut])
def list_wrong_book(
    subject_code: str | None = Query(default=None, max_length=40),
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
) -> list[WrongBookItemOut]:
    items = WrongBookService.list_items(db, student.id, subject_code=subject_code)
    return [WrongBookItemOut.model_validate(i) for i in items]

