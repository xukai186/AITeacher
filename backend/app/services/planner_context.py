from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MasterPlan, MasterPlanVersion, StudentSubject
from app.services.agent_context import get_subject_context
from app.services.plan_review_jobs import PlanReviewJobService


def get_master_plan_summary(db: Session, *, student_user_id: uuid.UUID) -> dict[str, Any]:
    plan = db.execute(
        select(MasterPlan).where(MasterPlan.student_user_id == student_user_id)
    ).scalar_one_or_none()
    if plan is None:
        return {"exists": False}

    version: MasterPlanVersion | None = None
    if plan.current_version_id is not None:
        version = db.get(MasterPlanVersion, plan.current_version_id)

    return {
        "exists": True,
        "plan_id": str(plan.id),
        "status": plan.status,
        "version": version.version if version else None,
        "weekly_goals": version.weekly_goals_json if version else None,
        "daily_time_budget": version.daily_time_budget_json if version else None,
    }


def get_student_overview(db: Session, *, student_user_id: uuid.UUID) -> dict[str, Any]:
    subject_codes = list(
        db.execute(
            select(StudentSubject.subject_code).where(
                StudentSubject.student_user_id == student_user_id,
                StudentSubject.enabled.is_(True),
            )
        )
        .scalars()
        .all()
    )
    subjects: list[dict[str, Any]] = []
    for code in subject_codes:
        ctx = get_subject_context(db, student_user_id=student_user_id, subject_code=code)
        subjects.append(
            {
                "subject_code": code,
                "wrong_source_counts": ctx.wrong_source_counts,
                "weak_node_count": ctx.weak_node_count,
                "recommendation_count": ctx.recommendation_count,
            }
        )
    return {"subject_codes": subject_codes, "subjects": subjects}


def trigger_plan_review(
    db: Session,
    *,
    student_user_id: uuid.UUID,
    subject_code: str | None = None,
    target_date: date | None = None,
) -> list[dict[str, Any]]:
    from datetime import timedelta

    day = target_date or (date.today() + timedelta(days=1))

    if subject_code:
        codes = [subject_code]
    else:
        codes = list(
            db.execute(
                select(StudentSubject.subject_code).where(
                    StudentSubject.student_user_id == student_user_id,
                    StudentSubject.enabled.is_(True),
                )
            )
            .scalars()
            .all()
        )

    svc = PlanReviewJobService()
    out: list[dict[str, Any]] = []
    for code in codes:
        enqueued = svc.enqueue(
            db,
            student_user_id=student_user_id,
            subject_code=code,
            target_date=day,
            trigger="planner_chat",
        )
        job = svc.get_for_student(db, job_id=enqueued.job_id, student_user_id=student_user_id)
        out.append(
            {
                "job_id": str(enqueued.job_id),
                "subject_code": code,
                "target_date": day.isoformat(),
                "status": job.status if job else "pending",
                "created": enqueued.created,
            }
        )
    return out
