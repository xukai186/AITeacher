from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import DailyTask, MasterPlan, MasterPlanVersion

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


class MasterPlannerService:
    """总规划 Agent（规则版）：按当日预算削减低优先级 pending 任务。"""

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
        # Cancel lowest-priority tasks first; tie-break by larger est_minutes.
        tasks_sorted = sorted(
            tasks,
            key=lambda t: (
                TASK_PRIORITY.get(t.type, 99),
                -t.est_minutes,
                t.created_at,
            ),
            reverse=True,
        )

        scheduled = before
        for task in tasks_sorted:
            if scheduled <= budget:
                break
            task.status = "cancelled"
            scheduled -= task.est_minutes
            result.cancelled_count += 1
            result.cancelled_task_ids.append(task.id)

        db.flush()
        result.scheduled_minutes_after = scheduled_minutes_for_date(db, student_user_id, target_date)
        return result
