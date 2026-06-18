from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyTask, MasterPlan, MasterPlanVersion, SubjectPlan, SubjectPlanVersion
from app.services.master_plan_activation import MasterPlanActivationService
from app.services.plan_review_jobs import PlanReviewJobService


def get_weekly_calendar(db: Session, *, student_user_id: uuid.UUID) -> dict[str, Any]:
    today = date.today()
    end = today + timedelta(days=6)
    tasks = (
        db.execute(
            select(DailyTask)
            .where(
                DailyTask.student_user_id == student_user_id,
                DailyTask.date >= today,
                DailyTask.date <= end,
            )
            .order_by(DailyTask.date, DailyTask.created_at)
        )
        .scalars()
        .all()
    )
    by_date: dict[str, list[dict[str, Any]]] = {}
    for task in tasks:
        key = task.date.isoformat()
        by_date.setdefault(key, []).append(
            {
                "id": str(task.id),
                "subject_code": task.subject_code,
                "type": task.type,
                "title": task.title,
                "status": task.status,
                "est_minutes": task.est_minutes,
            }
        )
    days = []
    for offset in range(7):
        day = today + timedelta(days=offset)
        key = day.isoformat()
        items = by_date.get(key, [])
        days.append(
            {
                "date": key,
                "task_count": len(items),
                "pending_count": sum(1 for t in items if t["status"] == "pending"),
                "scheduled_minutes": sum(t["est_minutes"] for t in items),
                "tasks": items,
            }
        )
    return {"start_date": today.isoformat(), "end_date": end.isoformat(), "days": days}


def propose_master_plan(
    db: Session,
    *,
    student_user_id: uuid.UUID,
    daily_minutes: int | None = None,
    target_date: date | None = None,
    weekly_goals: list[dict] | None = None,
) -> dict[str, Any]:
    plan = db.execute(
        select(MasterPlan).where(MasterPlan.student_user_id == student_user_id)
    ).scalar_one_or_none()
    if plan is None or plan.current_version_id is None:
        return {"ok": False, "error": "master plan not found"}

    current = db.get(MasterPlanVersion, plan.current_version_id)
    if current is None:
        return {"ok": False, "error": "active master plan version missing"}

    day = target_date or (date.today() + timedelta(days=1))
    new_budget = list(current.daily_time_budget_json or [])
    if daily_minutes is not None:
        new_budget = MasterPlanActivationService.set_budget_minutes_for_date(
            new_budget, day, daily_minutes
        )

    new_weekly = weekly_goals if weekly_goals is not None else current.weekly_goals_json
    result = MasterPlanActivationService().propose_version(
        db,
        plan=plan,
        daily_time_budget_json=new_budget,
        weekly_goals_json=new_weekly,
        source="ai",
    )
    db.flush()
    return {
        "ok": True,
        "version_id": str(result.version_id),
        "auto_activated": result.auto_activated,
        "pending_confirmation": result.pending,
        "change_ratio": round(result.change_ratio, 4),
        "requires_student_confirmation": result.pending,
    }


def propose_subject_plan(
    db: Session,
    *,
    student_user_id: uuid.UUID,
    subject_code: str,
    phases: list[dict],
) -> dict[str, Any]:
    if not phases:
        return {"ok": False, "error": "phases must not be empty"}

    plan = db.execute(
        select(SubjectPlan).where(
            SubjectPlan.student_user_id == student_user_id,
            SubjectPlan.subject_code == subject_code,
        )
    ).scalar_one_or_none()
    if plan is None:
        plan = SubjectPlan(student_user_id=student_user_id, subject_code=subject_code)
        db.add(plan)
        db.flush()

    current = (
        db.get(SubjectPlanVersion, plan.current_version_id)
        if plan.current_version_id
        else None
    )
    next_version = (current.version + 1) if current is not None else 1
    version = SubjectPlanVersion(
        plan_id=plan.id,
        version=next_version,
        source="ai",
        phases_json=phases,
    )
    db.add(version)
    db.flush()
    plan.current_version_id = version.id
    db.flush()
    return {
        "ok": True,
        "subject_code": subject_code,
        "version": next_version,
        "phases": phases,
    }


def request_plan_adjustment(
    db: Session,
    *,
    student_user_id: uuid.UUID,
    subject_code: str,
    target_date: date | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    day = target_date or (date.today() + timedelta(days=1))
    enqueued = PlanReviewJobService().enqueue(
        db,
        student_user_id=student_user_id,
        subject_code=subject_code,
        target_date=day,
        trigger="chat_request",
    )
    job = PlanReviewJobService().get_for_student(
        db, job_id=enqueued.job_id, student_user_id=student_user_id
    )
    return {
        "ok": True,
        "job_id": str(enqueued.job_id),
        "subject_code": subject_code,
        "target_date": day.isoformat(),
        "status": job.status if job else "pending",
        "created": enqueued.created,
        "reason": reason,
    }
