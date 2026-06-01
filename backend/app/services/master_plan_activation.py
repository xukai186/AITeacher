from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MasterPlan, MasterPlanVersion

AUTO_ACTIVATE_THRESHOLD = 0.15


@dataclass(frozen=True)
class ProposeResult:
    version_id: uuid.UUID
    auto_activated: bool
    change_ratio: float
    pending: bool


class MasterPlanActivationService:
    @staticmethod
    def total_budget_minutes(budget_json: list[dict] | None) -> int:
        if not budget_json:
            return 0
        return sum(int(entry.get("minutes", 0)) for entry in budget_json)

    @classmethod
    def budget_change_ratio(
        cls,
        old_json: list[dict] | None,
        new_json: list[dict] | None,
    ) -> float:
        old_total = cls.total_budget_minutes(old_json)
        new_total = cls.total_budget_minutes(new_json)
        if old_total == 0:
            return 1.0 if new_total > 0 else 0.0
        return abs(new_total - old_total) / old_total

    @staticmethod
    def set_budget_minutes_for_date(
        budget_json: list[dict] | None,
        day: date,
        minutes: int,
    ) -> list[dict]:
        day_str = day.isoformat()
        out: list[dict] = []
        found = False
        for entry in budget_json or []:
            if entry.get("date") == day_str:
                out.append({"date": day_str, "minutes": minutes})
                found = True
            else:
                out.append(dict(entry))
        if not found:
            out.append({"date": day_str, "minutes": minutes})
        return out

    def propose_daily_budget(
        self,
        db: Session,
        *,
        student_user_id: uuid.UUID,
        target_date: date,
        new_minutes_for_day: int,
        source: str = "ai",
    ) -> ProposeResult | None:
        plan = db.execute(
            select(MasterPlan).where(MasterPlan.student_user_id == student_user_id)
        ).scalar_one_or_none()
        if plan is None or plan.current_version_id is None:
            return None

        current = db.get(MasterPlanVersion, plan.current_version_id)
        if current is None:
            return None

        new_budget = self.set_budget_minutes_for_date(
            current.daily_time_budget_json,
            target_date,
            new_minutes_for_day,
        )
        return self.propose_version(
            db,
            plan=plan,
            daily_time_budget_json=new_budget,
            weekly_goals_json=current.weekly_goals_json,
            source=source,
        )

    def propose_version(
        self,
        db: Session,
        *,
        plan: MasterPlan,
        daily_time_budget_json: list[dict],
        weekly_goals_json: list[dict] | None,
        source: str,
    ) -> ProposeResult:
        current = None
        if plan.current_version_id:
            current = db.get(MasterPlanVersion, plan.current_version_id)

        change_ratio = self.budget_change_ratio(
            current.daily_time_budget_json if current else None,
            daily_time_budget_json,
        )
        next_ver = 1
        if current is not None:
            next_ver = current.version + 1

        if plan.pending_version_id:
            old_pending = db.get(MasterPlanVersion, plan.pending_version_id)
            if old_pending is not None:
                db.delete(old_pending)
                db.flush()

        version = MasterPlanVersion(
            plan_id=plan.id,
            version=next_ver,
            source=source,
            weekly_goals_json=weekly_goals_json or [],
            daily_time_budget_json=daily_time_budget_json,
        )
        db.add(version)
        db.flush()

        auto = change_ratio <= AUTO_ACTIVATE_THRESHOLD
        if auto:
            plan.current_version_id = version.id
            plan.pending_version_id = None
        else:
            plan.pending_version_id = version.id

        db.flush()
        return ProposeResult(
            version_id=version.id,
            auto_activated=auto,
            change_ratio=change_ratio,
            pending=not auto,
        )

    def get_state(self, db: Session, *, student_user_id: uuid.UUID) -> dict:
        plan = db.execute(
            select(MasterPlan).where(MasterPlan.student_user_id == student_user_id)
        ).scalar_one_or_none()
        if plan is None:
            return {
                "plan_id": None,
                "plan_status": None,
                "active_version": None,
                "pending_version": None,
                "budget_change_ratio": None,
                "requires_confirmation": False,
            }

        active = (
            db.get(MasterPlanVersion, plan.current_version_id)
            if plan.current_version_id
            else None
        )
        pending = (
            db.get(MasterPlanVersion, plan.pending_version_id)
            if plan.pending_version_id
            else None
        )
        ratio = None
        requires = pending is not None
        if active and pending:
            ratio = self.budget_change_ratio(
                active.daily_time_budget_json,
                pending.daily_time_budget_json,
            )

        return {
            "plan_id": plan.id,
            "plan_status": plan.status,
            "active_version": active,
            "pending_version": pending,
            "budget_change_ratio": ratio,
            "requires_confirmation": requires,
        }

    def confirm_pending(self, db: Session, *, student_user_id: uuid.UUID) -> MasterPlanVersion:
        plan = db.execute(
            select(MasterPlan).where(MasterPlan.student_user_id == student_user_id)
        ).scalar_one_or_none()
        if plan is None or plan.pending_version_id is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "no pending plan to confirm")

        pending = db.get(MasterPlanVersion, plan.pending_version_id)
        if pending is None:
            plan.pending_version_id = None
            raise HTTPException(status.HTTP_404_NOT_FOUND, "pending version missing")

        plan.current_version_id = pending.id
        plan.pending_version_id = None
        db.flush()
        return pending

    def reject_pending(self, db: Session, *, student_user_id: uuid.UUID) -> None:
        plan = db.execute(
            select(MasterPlan).where(MasterPlan.student_user_id == student_user_id)
        ).scalar_one_or_none()
        if plan is None or plan.pending_version_id is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "no pending plan to reject")

        pending = db.get(MasterPlanVersion, plan.pending_version_id)
        plan.pending_version_id = None
        if pending is not None:
            db.delete(pending)
        db.flush()
