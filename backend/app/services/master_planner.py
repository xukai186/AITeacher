from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import DailyTask, MasterPlan, MasterPlanVersion, Package, StudentProfile, StudentSubject

# Lower number = higher priority (kept longer when trimming).
TASK_PRIORITY: dict[str, int] = {
    "review_wrong": 0,
    "self_test": 1,
    "check_result": 2,
    "study": 3,
}


@dataclass
class TrimBudgetResult:
    target_date: date
    budget_minutes: int | None
    scheduled_minutes_before: int
    scheduled_minutes_after: int
    cancelled_count: int = 0
    cancelled_task_ids: list[uuid.UUID] = field(default_factory=list)
    cancelled_by_subject: dict[str, int] = field(default_factory=dict)


def budget_minutes_for_date(db: Session, student_user_id: uuid.UUID, day: date) -> int | None:
    plan = db.execute(
        select(MasterPlan).where(MasterPlan.student_user_id == student_user_id)
    ).scalar_one_or_none()
    if plan is None or plan.current_version_id is None:
        return None
    version = db.get(MasterPlanVersion, plan.current_version_id)
    if version is None or not version.daily_time_budget_json:
        return None
    day_str = day.isoformat()
    for entry in version.daily_time_budget_json:
        if entry.get("date") == day_str:
            return int(entry.get("minutes", 0))
    return None


def scheduled_minutes_for_date(db: Session, student_user_id: uuid.UUID, day: date) -> int:
    total = db.execute(
        select(func.coalesce(func.sum(DailyTask.est_minutes), 0)).where(
            DailyTask.student_user_id == student_user_id,
            DailyTask.date == day,
            DailyTask.status != "cancelled",
        )
    ).scalar_one()
    return int(total)


def subject_weights_for_student(db: Session, student_user_id: uuid.UUID) -> dict[str, int]:
    """Higher weight = more protected when trimming across subjects (package order)."""
    profile = db.execute(
        select(StudentProfile).where(StudentProfile.user_id == student_user_id)
    ).scalar_one_or_none()

    codes: list[str] = []
    if profile is not None and profile.package_id is not None:
        pkg = db.get(Package, profile.package_id)
        if pkg is not None and pkg.subject_codes:
            codes = list(pkg.subject_codes)

    if not codes:
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

    if not codes:
        return {}

    n = len(codes)
    return {code: n - idx for idx, code in enumerate(codes)}


def _cancel_sort_key(task: DailyTask, weights: dict[str, int]) -> tuple:
    # Cancel low subject weight first, then low task-type priority (study before review_wrong).
    return (
        weights.get(task.subject_code, 0),
        -TASK_PRIORITY.get(task.type, 99),
        -task.est_minutes,
        task.created_at,
    )


class MasterPlannerService:
    """总规划 Agent（规则版）：跨科当日预算内按科目权重 + 任务优先级削减。"""

    def trim_tasks_by_budget(
        self,
        db: Session,
        *,
        student_user_id: uuid.UUID,
        target_date: date,
    ) -> TrimBudgetResult:
        budget = budget_minutes_for_date(db, student_user_id, target_date)
        before = scheduled_minutes_for_date(db, student_user_id, target_date)
        result = TrimBudgetResult(
            target_date=target_date,
            budget_minutes=budget,
            scheduled_minutes_before=before,
            scheduled_minutes_after=before,
        )
        if budget is None or before <= budget:
            return result

        weights = subject_weights_for_student(db, student_user_id)
        tasks = (
            db.execute(
                select(DailyTask).where(
                    DailyTask.student_user_id == student_user_id,
                    DailyTask.date == target_date,
                    DailyTask.status == "pending",
                )
            )
            .scalars()
            .all()
        )
        tasks_sorted = sorted(tasks, key=lambda t: _cancel_sort_key(t, weights))

        scheduled = before
        for task in tasks_sorted:
            if scheduled <= budget:
                break
            task.status = "cancelled"
            scheduled -= task.est_minutes
            result.cancelled_count += 1
            result.cancelled_task_ids.append(task.id)
            result.cancelled_by_subject[task.subject_code] = (
                result.cancelled_by_subject.get(task.subject_code, 0) + 1
            )

        db.flush()
        result.scheduled_minutes_after = scheduled_minutes_for_date(db, student_user_id, target_date)
        return result
