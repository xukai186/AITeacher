from __future__ import annotations

import json
import uuid
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.services.agent_context import SubjectContext, get_subject_context
from app.services.plan_review import PlanReviewResult, PlanReviewService


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
