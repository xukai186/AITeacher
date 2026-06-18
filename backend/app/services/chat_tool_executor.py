from __future__ import annotations

import json
import uuid
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.services.agent_context import SubjectContext, get_subject_context
from app.services.chat_paper_tools import explain_question
from app.services.chat_plan_tools import (
    get_weekly_calendar,
    propose_master_plan,
    propose_subject_plan,
    request_plan_adjustment,
)
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
            from app.models import SelfTestQuestion
            from app.services.paper_gen_jobs import run_paper_gen_job_if_needed
            from app.services.self_test import SelfTestService

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

        if tool_name == "list_papers":
            if agent_type != "subject":
                return {"error": "list_papers is only available for subject agent"}
            subject_code = default_subject_code
            if not subject_code:
                return {"error": "subject_code is required"}

            raw_limit = arguments.get("limit")
            limit = int(raw_limit) if raw_limit is not None else 5
            limit = max(1, min(limit, 20))

            from app.models import PlacementPaper, SelfTestPaper

            placements = (
                db.execute(
                    select(PlacementPaper)
                    .where(
                        PlacementPaper.student_user_id == student_user_id,
                        PlacementPaper.subject_code == subject_code,
                    )
                    .order_by(PlacementPaper.created_at.desc())
                    .limit(limit)
                )
                .scalars()
                .all()
            )
            self_tests = (
                db.execute(
                    select(SelfTestPaper)
                    .where(
                        SelfTestPaper.student_user_id == student_user_id,
                        SelfTestPaper.subject_code == subject_code,
                    )
                    .order_by(SelfTestPaper.created_at.desc())
                    .limit(limit)
                )
                .scalars()
                .all()
            )
            return {
                "subject_code": subject_code,
                "placement_papers": [
                    {"paper_id": str(p.id), "status": p.status, "created_at": p.created_at.isoformat()}
                    for p in placements
                ],
                "self_test_papers": [
                    {"paper_id": str(p.id), "status": p.status, "created_at": p.created_at.isoformat()}
                    for p in self_tests
                ],
            }

        if tool_name == "get_paper":
            if agent_type != "subject":
                return {"error": "get_paper is only available for subject agent"}
            subject_code = default_subject_code
            if not subject_code:
                return {"error": "subject_code is required"}

            paper_type = arguments.get("paper_type")
            paper_id_raw = arguments.get("paper_id")
            if not paper_type or not paper_id_raw:
                return {"error": "paper_type and paper_id are required"}

            try:
                paper_id = uuid.UUID(str(paper_id_raw))
            except Exception:
                return {"error": "invalid paper_id"}

            from app.models import (
                PlacementPaper,
                PlacementQuestion,
                SelfTestPaper,
                SelfTestQuestion,
            )

            if paper_type == "placement":
                paper = db.get(PlacementPaper, paper_id)
                if paper is None or paper.student_user_id != student_user_id or paper.subject_code != subject_code:
                    return {"error": "paper not found"}
                qs = (
                    db.execute(
                        select(PlacementQuestion)
                        .where(PlacementQuestion.paper_id == paper_id)
                        .order_by(PlacementQuestion.seq)
                    )
                    .scalars()
                    .all()
                )
                return {
                    "paper_type": "placement",
                    "paper_id": str(paper.id),
                    "status": paper.status,
                    "subject_code": paper.subject_code,
                    "questions": [
                        {
                            "seq": q.seq,
                            "q_type": q.q_type,
                            "stem": q.stem,
                            "choices": q.choices_json or [],
                        }
                        for q in qs
                    ],
                }

            if paper_type == "self_test":
                paper = db.get(SelfTestPaper, paper_id)
                if paper is None or paper.student_user_id != student_user_id or paper.subject_code != subject_code:
                    return {"error": "paper not found"}
                qs = (
                    db.execute(
                        select(SelfTestQuestion)
                        .where(SelfTestQuestion.paper_id == paper_id)
                        .order_by(SelfTestQuestion.seq)
                    )
                    .scalars()
                    .all()
                )
                return {
                    "paper_type": "self_test",
                    "paper_id": str(paper.id),
                    "status": paper.status,
                    "subject_code": paper.subject_code,
                    "questions": [
                        {
                            "seq": q.seq,
                            "q_type": q.q_type,
                            "stem": q.stem,
                            "choices": q.choices_json or [],
                            "points": q.points,
                        }
                        for q in qs
                    ],
                }

            return {"error": "unsupported paper_type"}

        if tool_name == "explain_question":
            if agent_type != "subject":
                return {"error": "explain_question is only available for subject agent"}
            subject_code = default_subject_code
            if not subject_code:
                return {"error": "subject_code is required"}
            paper_type = arguments.get("paper_type")
            paper_id_raw = arguments.get("paper_id")
            if not paper_type or not paper_id_raw:
                return {"error": "paper_type and paper_id are required"}
            try:
                paper_id = uuid.UUID(str(paper_id_raw))
            except Exception:
                return {"error": "invalid paper_id"}
            question_seq = arguments.get("question_seq")
            question_id_raw = arguments.get("question_id")
            question_id = None
            if question_id_raw:
                try:
                    question_id = uuid.UUID(str(question_id_raw))
                except Exception:
                    return {"error": "invalid question_id"}
            return explain_question(
                db,
                student_user_id=student_user_id,
                subject_code=subject_code,
                paper_type=str(paper_type),
                paper_id=paper_id,
                question_seq=int(question_seq) if question_seq is not None else None,
                question_id=question_id,
            )

        if tool_name == "propose_subject_plan":
            if agent_type != "subject":
                return {"error": "propose_subject_plan is only available for subject agent"}
            subject_code = default_subject_code
            if not subject_code:
                return {"error": "subject_code is required"}
            phases = arguments.get("phases")
            if not isinstance(phases, list):
                return {"error": "phases must be a list"}
            return propose_subject_plan(
                db,
                student_user_id=student_user_id,
                subject_code=subject_code,
                phases=phases,
            )

        if tool_name == "request_plan_adjustment":
            if agent_type != "subject":
                return {"error": "request_plan_adjustment is only available for subject agent"}
            subject_code = default_subject_code
            if not subject_code:
                return {"error": "subject_code is required"}
            target = _parse_target_date(arguments.get("target_date"))
            return request_plan_adjustment(
                db,
                student_user_id=student_user_id,
                subject_code=subject_code,
                target_date=target,
                reason=arguments.get("reason"),
            )

        if tool_name == "get_weekly_calendar":
            if agent_type != "planner":
                return {"error": "get_weekly_calendar is only available for planner agent"}
            return get_weekly_calendar(db, student_user_id=student_user_id)

        if tool_name == "propose_master_plan":
            if agent_type != "planner":
                return {"error": "propose_master_plan is only available for planner agent"}
            target = _parse_target_date(arguments.get("target_date"))
            daily_minutes = arguments.get("daily_minutes")
            weekly_goals = arguments.get("weekly_goals")
            if daily_minutes is None and weekly_goals is None:
                return {"error": "daily_minutes or weekly_goals is required"}
            return propose_master_plan(
                db,
                student_user_id=student_user_id,
                daily_minutes=int(daily_minutes) if daily_minutes is not None else None,
                target_date=target,
                weekly_goals=weekly_goals if isinstance(weekly_goals, list) else None,
            )

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
