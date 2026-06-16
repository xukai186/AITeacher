from __future__ import annotations

import json
import uuid
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.services.agent_context import SubjectContext, get_subject_context
from app.services.plan_review import PlanReviewResult, PlanReviewService
from app.services.self_test_eligibility import SelfTestEligibilityService
from app.services.planner_context import (
    get_master_plan_summary,
    get_student_overview,
    trigger_plan_review,
)


def _parse_target_date(raw: str | None) -> date | None:
    if not raw:
        return None
    return date.fromisoformat(raw)


def _serialize_context(ctx: SubjectContext) -> dict[str, Any]:
    return {
        "subject_code": ctx.subject_code,
        "wrong_source_counts": ctx.wrong_source_counts,
        "weak_node_count": ctx.weak_node_count,
        "recommendation_count": ctx.recommendation_count,
    }


def _serialize_plan_review(result: PlanReviewResult) -> dict[str, Any]:
    return {
        "target_date": result.target_date.isoformat(),
        "subject_code": result.subject_code,
        "created_count": result.apply.created_count,
        "skipped_count": result.apply.skipped_count,
        "scheduled_minutes": result.trim.scheduled_minutes_after,
        "budget_minutes": result.apply.budget_minutes,
        "cancelled_count": result.trim.cancelled_count,
        "warnings": result.warnings,
    }


class ChatToolExecutor:
    """Execute chat-allowed tools for a student (not exposed as HTTP APIs)."""

    def execute(
        self,
        db: Session,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        student_user_id: uuid.UUID,
        default_subject_code: str | None,
        agent_type: str,
    ) -> dict[str, Any]:
        if tool_name == "get_subject_context":
            subject_code = arguments.get("subject_code") or default_subject_code
            if not subject_code:
                return {"error": "subject_code is required"}
            ctx = get_subject_context(
                db, student_user_id=student_user_id, subject_code=str(subject_code)
            )
            return _serialize_context(ctx)

        if tool_name == "get_master_plan":
            if agent_type != "planner":
                return {"error": "get_master_plan is only available for planner agent"}
            return get_master_plan_summary(db, student_user_id=student_user_id)

        if tool_name == "get_student_overview":
            if agent_type != "planner":
                return {"error": "get_student_overview is only available for planner agent"}
            return get_student_overview(db, student_user_id=student_user_id)

        if tool_name == "trigger_plan_review":
            if agent_type != "planner":
                return {"error": "trigger_plan_review is only available for planner agent"}
            subject = arguments.get("subject_code")
            target = _parse_target_date(arguments.get("target_date"))
            results = trigger_plan_review(
                db,
                student_user_id=student_user_id,
                subject_code=str(subject) if subject else None,
                target_date=target,
            )
            return {"reviews": results}

        if tool_name == "generate_daily_tasks":
            if agent_type != "subject":
                return {"error": "generate_daily_tasks is only available for subject agent"}
            subject_code = default_subject_code
            if not subject_code:
                return {"error": "subject_code is required"}
            target = _parse_target_date(arguments.get("target_date"))
            review = PlanReviewService().run_subject_review(
                db,
                student_user_id=student_user_id,
                subject_code=subject_code,
                trigger="chat",
                target_date=target,
            )
            return _serialize_plan_review(review)

        if tool_name == "generate_paper":
            if agent_type != "subject":
                return {"error": "generate_paper is only available for subject agent"}
            subject_code = default_subject_code
            if not subject_code:
                return {"error": "subject_code is required"}
            eligibility = SelfTestEligibilityService().check(
                db, student_user_id=student_user_id, subject_code=subject_code
            )
            if not eligibility.allowed:
                return {"ok": False, "reasons": eligibility.reasons}
            from app.services.self_test import SelfTestService
            from app.services.paper_gen_jobs import run_paper_gen_job_if_needed
            from sqlalchemy import func, select
            from app.models import SelfTestQuestion

            paper, gen_job_id = SelfTestService.generate(db, student_user_id, subject_code)
            run_paper_gen_job_if_needed(db, gen_job_id)
            q_count = db.execute(
                select(func.count(SelfTestQuestion.id)).where(
                    SelfTestQuestion.paper_id == paper.id
                )
            ).scalar_one()
            return {
                "ok": True,
                "paper_id": str(paper.id),
                "subject_code": paper.subject_code,
                "status": paper.status,
                "question_count": int(q_count),
            }

        return {"error": f"unknown tool: {tool_name}"}

    @staticmethod
    def parse_arguments(raw: str | dict[str, Any] | None) -> dict[str, Any]:
        if raw is None:
            return {}
        if isinstance(raw, dict):
            return raw
        raw = raw.strip()
        if not raw:
            return {}
        return json.loads(raw)
