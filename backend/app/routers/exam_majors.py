from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.database import get_db
from app.models import ExamMajor, ExamMajorCategory, User
from app.schemas.exam_profile import ExamMajorCategoryOut, ExamMajorOut

router = APIRouter(prefix="/exam-majors", tags=["exam-majors"])


@router.get("/categories", response_model=list[ExamMajorCategoryOut])
def list_major_categories(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[ExamMajorCategoryOut]:
    rows = (
        db.execute(select(ExamMajorCategory).order_by(ExamMajorCategory.sort_order, ExamMajorCategory.code))
        .scalars()
        .all()
    )
    return [ExamMajorCategoryOut.model_validate(row) for row in rows]


@router.get("", response_model=list[ExamMajorOut])
def list_majors_by_category(
    category: str = Query(..., min_length=1, max_length=60),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[ExamMajorOut]:
    rows = (
        db.execute(
            select(ExamMajor)
            .where(ExamMajor.category_code == category)
            .order_by(ExamMajor.name, ExamMajor.code)
        )
        .scalars()
        .all()
    )
    return [ExamMajorOut.model_validate(row) for row in rows]
