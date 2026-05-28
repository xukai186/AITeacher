from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.permissions import require_roles
from app.database import get_db
from app.models import User, UserRole
from app.schemas.report import ReportOverviewOut
from app.services.report import ReportQuery, ReportService

router = APIRouter(prefix="/student/report", tags=["student-report"])


@router.get("/overview", response_model=ReportOverviewOut)
def get_report_overview(
    subject_code: str | None = Query(default=None, max_length=40),
    trend_limit: int = Query(default=10, ge=1, le=30),
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
) -> ReportOverviewOut:
    return ReportService.overview(
        db,
        ReportQuery(
            student_user_id=student.id,
            subject_code=subject_code,
            trend_limit=trend_limit,
        ),
    )

