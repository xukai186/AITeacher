from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.services.agent_tools import default_tool_registry
from app.services.master_planner import TrimBudgetResult, scheduled_minutes_for_date
from app.services.subject_agent import ApplyRecommendationsResult


@dataclass
class PlanReviewResult:
    trigger: str
    subject_code: str
    target_date: date
    apply: ApplyRecommendationsResult
    trim: TrimBudgetResult
    warnings: list[str] = field(default_factory=list)


class PlanReviewService:
    """计划复审（内部 Pipeline）：学科 Agent 工具链 + 总规划预算削减。"""

    def run_subject_review(
        self,
        db: Session,
        *,
        student_user_id: uuid.UUID,
        subject_code: str,
        trigger: str,
        target_date: date | None = None,
    ) -> PlanReviewResult:
        day = target_date or (date.today() + timedelta(days=1))
        tools = default_tool_registry

        apply: ApplyRecommendationsResult = tools.call(
            db,
            "generate_daily_tasks",
            student_user_id=student_user_id,
            subject_code=subject_code,
            target_date=day,
        )
        budget = apply.budget_minutes
        scheduled_now = scheduled_minutes_for_date(db, student_user_id, day)
        trim = TrimBudgetResult(
            target_date=day,
            budget_minutes=budget,
            scheduled_minutes_before=scheduled_now,
            scheduled_minutes_after=scheduled_now,
        )

        warnings = list(apply.warnings)

        return PlanReviewResult(
            trigger=trigger,
            subject_code=subject_code,
            target_date=day,
            apply=apply,
            trim=trim,
            warnings=warnings,
        )
