from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.permissions import require_roles
from app.database import get_db
from app.models import User, UserRole
from app.schemas.student_paper import StudentPaperSummaryOut
from app.services.student_papers import StudentPaperService

router = APIRouter(prefix="/student/papers", tags=["student-papers"])


@router.get("", response_model=list[StudentPaperSummaryOut])
def list_student_papers(
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
    subject_code: str | None = Query(default=None, max_length=40),
    paper_type: str | None = Query(default=None, pattern="^(placement|self_test)$"),
    status: str | None = Query(default=None, max_length=40),
) -> list[StudentPaperSummaryOut]:
    return StudentPaperService().list_papers(
        db,
        student_user_id=student.id,
        subject_code=subject_code,
        paper_type=paper_type,
        status=status,
    )
