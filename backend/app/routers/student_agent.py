from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.permissions import require_roles
from app.database import get_db
from app.models import User, UserRole
from app.schemas.agent import ApplyRecommendationsOut
from app.services.plan_review import PlanReviewService

router = APIRouter(prefix="/student/agent", tags=["student-agent"])


@router.post("/apply-recommendations", response_model=ApplyRecommendationsOut)
def apply_recommendations_as_tasks(
    subject_code: str = Query(..., min_length=1, max_length=40),
    target_date: date | None = Query(None),
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
) -> ApplyRecommendationsOut:
    review = PlanReviewService().run_subject_review(
        db,
        student_user_id=student.id,
        subject_code=subject_code,
        trigger="manual_apply",
        target_date=target_date,
    )
    apply = review.apply
    db.commit()
    return ApplyRecommendationsOut(
        target_date=apply.target_date,
        subject_code=apply.subject_code,
        created=apply.created,
        created_count=apply.created_count,
        skipped_count=apply.skipped_count,
        budget_minutes=apply.budget_minutes,
        scheduled_minutes=review.trim.scheduled_minutes_after,
        over_budget=apply.over_budget or review.trim.cancelled_count > 0,
        warnings=review.warnings,
    )
