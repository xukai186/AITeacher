from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
import uuid

from app.auth.permissions import require_roles
from app.database import get_db
from app.models import User, UserRole
from app.schemas.wrong_book import (
    WrongBookItemOut,
    WrongBookPracticeIn,
    WrongBookPracticeOut,
)
from app.services.wrong_book import WrongBookService
from app.services.wrong_book_mastery import WrongBookMasteryService

router = APIRouter(prefix="/student/wrong-book", tags=["student-wrong-book"])


@router.get("", response_model=list[WrongBookItemOut])
def list_wrong_book(
    subject_code: str | None = Query(default=None, max_length=40),
    source_type: str | None = Query(default=None, max_length=40),
    knowledge_node_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None, max_length=40),
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
        status=status,
        limit=limit,
        offset=offset,
    )
    return [WrongBookItemOut.model_validate(i) for i in items]


@router.post("/{item_id}/practice", response_model=WrongBookPracticeOut)
def practice_wrong_item(
    item_id: uuid.UUID,
    payload: WrongBookPracticeIn,
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
) -> WrongBookPracticeOut:
    item = WrongBookService.get_item(db, student.id, item_id)
    result = WrongBookMasteryService().practice(db, item=item, content=payload.content)
    db.commit()
    return WrongBookPracticeOut(
        is_correct=result.is_correct,
        status=result.status,
        consecutive_correct_count=result.consecutive_correct_count,
        mastered=result.mastered,
    )


@router.post("/{item_id}/archive", response_model=WrongBookItemOut)
def archive_wrong_item(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
) -> WrongBookItemOut:
    item = WrongBookService.get_item(db, student.id, item_id)
    archived = WrongBookMasteryService.archive(db, item=item)
    db.commit()
    return WrongBookItemOut.model_validate(archived)
