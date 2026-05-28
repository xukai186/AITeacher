from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
import uuid

from app.auth.permissions import require_roles
from app.database import get_db
from app.models import User, UserRole
from app.schemas.wrong_book import WrongBookItemOut
from app.services.wrong_book import WrongBookService

router = APIRouter(prefix="/student/wrong-book", tags=["student-wrong-book"])


@router.get("", response_model=list[WrongBookItemOut])
def list_wrong_book(
    subject_code: str | None = Query(default=None, max_length=40),
    source_type: str | None = Query(default=None, max_length=40),
    knowledge_node_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
) -> list[WrongBookItemOut]:
    items = WrongBookService.list_items(
        db,
        student.id,
        subject_code=subject_code,
        source_type=source_type,
        knowledge_node_id=knowledge_node_id,
        limit=limit,
        offset=offset,
    )
    return [WrongBookItemOut.model_validate(i) for i in items]

