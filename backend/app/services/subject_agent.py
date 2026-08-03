from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyTask, MasterPlan, MasterPlanVersion, SyllabusNode
from app.services.exam_profile import ExamProfileService
from app.services.master_planner import budget_minutes_for_date, scheduled_minutes_for_date
from app.services.report import ReportQuery, ReportService

REC_EST_MINUTES: dict[str, int] = {
    "review_wrong": 30,
    "self_test": 45,
    "check_result": 20,
}


@dataclass
class ApplyRecommendationsResult:
    target_date: date
    subject_code: str
    created: list[DailyTask] = field(default_factory=list)
    created_count: int = 0
    skipped_count: int = 0
    budget_minutes: int | None = None
    scheduled_minutes: int = 0
    over_budget: bool = False
    warnings: list[str] = field(default_factory=list)


def _task_ref_id(
    student_user_id: uuid.UUID,
    day: date,
    subject_code: str,
    rec_type: str,
    knowledge_node_id: str | None,
) -> uuid.UUID:
    key = (
        f"daily_task_rec:{student_user_id}:{day.isoformat()}:"
        f"{subject_code}:{rec_type}:{knowledge_node_id or ''}"
    )
    return uuid.uuid5(uuid.NAMESPACE_URL, key)


def _focus_node_ids_for_subject(
    db: Session,
    student_user_id: uuid.UUID,
    subject_code: str,
) -> list[str]:
    plan = db.execute(
        select(MasterPlan).where(MasterPlan.student_user_id == student_user_id)
    ).scalar_one_or_none()
    if plan is None or plan.current_version_id is None:
        return []
    version = db.get(MasterPlanVersion, plan.current_version_id)
    if version is None or not version.weekly_goals_json:
        return []
    for goal in version.weekly_goals_json:
        if goal.get("kind") != "focus":
            continue
        if goal.get("subject_code") != subject_code:
            continue
        raw_ids = goal.get("syllabus_node_ids") or []
        return [str(node_id) for node_id in raw_ids if node_id]
    return []


def _resolve_node_name(db: Session, node_id: str) -> str:
    try:
        node_uuid = uuid.UUID(node_id)
    except ValueError:
        return "知识点"
    node = db.get(SyllabusNode, node_uuid)
    return node.name if node is not None else "知识点"


class SubjectAgentService:
    """学科 Agent：将学情报告建议落成可执行的每日任务（幂等）。"""

    def apply_report_recommendations(
        self,
        db: Session,
        *,
        student_user_id: uuid.UUID,
        subject_code: str,
        target_date: date | None = None,
    ) -> ApplyRecommendationsResult:
        day = target_date or date.today()
        overview = ReportService.overview(
            db,
            ReportQuery(student_user_id=student_user_id, subject_code=subject_code),
        )
        result = ApplyRecommendationsResult(target_date=day, subject_code=subject_code)

        focus_ids = _focus_node_ids_for_subject(db, student_user_id, subject_code)
        if focus_ids:
            self._apply_focus_cascade(
                db,
                student_user_id=student_user_id,
                subject_code=subject_code,
                day=day,
                focus_ids=focus_ids,
                weak_nodes=overview.weak_nodes,
                result=result,
            )
        else:
            self._apply_report_recommendations(
                db,
                student_user_id=student_user_id,
                subject_code=subject_code,
                day=day,
                recommendations=overview.recommendations,
                result=result,
            )

        self._maybe_add_profile_boost(
            db,
            student_user_id=student_user_id,
            subject_code=subject_code,
            target_date=day,
            result=result,
        )

        result.budget_minutes = budget_minutes_for_date(db, student_user_id, day)
        result.scheduled_minutes = scheduled_minutes_for_date(db, student_user_id, day)
        if result.budget_minutes is not None and result.scheduled_minutes > result.budget_minutes:
            result.over_budget = True
            result.warnings.append(
                f"当日已排 {result.scheduled_minutes} 分钟，超过总规划预算 {result.budget_minutes} 分钟；"
                "总规划 Agent 后续可协调削减低优先级任务。"
            )

        return result

    def _apply_focus_cascade(
        self,
        db: Session,
        *,
        student_user_id: uuid.UUID,
        subject_code: str,
        day: date,
        focus_ids: list[str],
        weak_nodes: list,
        result: ApplyRecommendationsResult,
    ) -> None:
        start = day.weekday() % len(focus_ids)
        pick_count = min(2, len(focus_ids))
        picks = [focus_ids[(start + i) % len(focus_ids)] for i in range(pick_count)]

        for node_id in picks:
            name = _resolve_node_name(db, node_id)
            self._try_add_task(
                db,
                result,
                student_user_id=student_user_id,
                day=day,
                subject_code=subject_code,
                rec_type="study",
                knowledge_node_id=node_id,
                title=f"推进：{name}",
                payload={
                    "source": "weekly_goal",
                    "syllabus_node_id": node_id,
                },
            )

        if weak_nodes:
            chosen = None
            focus_set = set(focus_ids)
            for weak in weak_nodes:
                node_id = weak.knowledge_node_id
                if node_id is not None and str(node_id) in focus_set:
                    chosen = weak
                    break
            if chosen is None:
                chosen = weak_nodes[0]

            node_id = chosen.knowledge_node_id
            node_key = str(node_id) if node_id is not None else None
            name = chosen.knowledge_node_name or _resolve_node_name(db, node_key or "")
            self._try_add_task(
                db,
                result,
                student_user_id=student_user_id,
                day=day,
                subject_code=subject_code,
                rec_type="review_wrong",
                knowledge_node_id=node_key,
                title=f"优先复习：{name}",
                payload={
                    "source": "report_weak",
                    "knowledge_node_id": node_key,
                    "wrong_count": chosen.wrong_count,
                },
            )

    def _apply_report_recommendations(
        self,
        db: Session,
        *,
        student_user_id: uuid.UUID,
        subject_code: str,
        day: date,
        recommendations: list[dict],
        result: ApplyRecommendationsResult,
    ) -> None:
        for rec in recommendations:
            rec_type = str(rec.get("type") or "study")
            title = str(rec.get("title") or "学习任务")
            rec_subject = rec.get("subject_code") or subject_code
            if rec_subject != subject_code:
                continue

            knowledge_node_id = rec.get("knowledge_node_id")
            self._try_add_task(
                db,
                result,
                student_user_id=student_user_id,
                day=day,
                subject_code=subject_code,
                rec_type=rec_type,
                knowledge_node_id=knowledge_node_id,
                title=title,
                payload={
                    "source": "report_recommendation",
                    "recommendation_type": rec_type,
                    "detail": rec.get("detail"),
                    "knowledge_node_id": knowledge_node_id,
                },
            )

    @staticmethod
    def _try_add_task(
        db: Session,
        result: ApplyRecommendationsResult,
        *,
        student_user_id: uuid.UUID,
        day: date,
        subject_code: str,
        rec_type: str,
        knowledge_node_id: str | None,
        title: str,
        payload: dict,
    ) -> None:
        ref_id = _task_ref_id(
            student_user_id, day, subject_code, rec_type, knowledge_node_id
        )
        existing = db.execute(
            select(DailyTask.id).where(
                DailyTask.student_user_id == student_user_id,
                DailyTask.date == day,
                DailyTask.subject_code == subject_code,
                DailyTask.type == rec_type,
                DailyTask.ref_id == ref_id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            result.skipped_count += 1
            return

        task = DailyTask(
            student_user_id=student_user_id,
            date=day,
            subject_code=subject_code,
            type=rec_type,
            ref_id=ref_id,
            status="pending",
            est_minutes=REC_EST_MINUTES.get(rec_type, 30),
            title=title,
            payload_json=payload,
        )
        db.add(task)
        db.flush()
        result.created.append(task)
        result.created_count += 1

    @staticmethod
    def _maybe_add_profile_boost(
        db: Session,
        *,
        student_user_id: uuid.UUID,
        subject_code: str,
        target_date: date,
        result: ApplyRecommendationsResult,
    ) -> None:
        effective = ExamProfileService().get_effective(db, student_user_id)
        if effective is None:
            return

        should_boost = False
        title = ""
        if subject_code == "english" and effective.cet_status in (None, "not_taken"):
            should_boost = True
            title = "英语基础巩固"
        elif (
            subject_code == "math"
            and effective.math_track != "none"
            and effective.math_mastery_level in (None, "zero", "basic")
        ):
            should_boost = True
            title = "数学基础巩固"

        if not should_boost:
            return

        ref_id = _task_ref_id(
            student_user_id,
            target_date,
            subject_code,
            "study",
            "exam_profile_boost",
        )
        existing = db.execute(
            select(DailyTask.id).where(
                DailyTask.student_user_id == student_user_id,
                DailyTask.date == target_date,
                DailyTask.subject_code == subject_code,
                DailyTask.type == "study",
                DailyTask.ref_id == ref_id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            result.skipped_count += 1
            return

        task = DailyTask(
            student_user_id=student_user_id,
            date=target_date,
            subject_code=subject_code,
            type="study",
            ref_id=ref_id,
            status="pending",
            est_minutes=30,
            title=title,
            payload_json={"source": "exam_profile_boost"},
        )
        db.add(task)
        db.flush()
        result.created.append(task)
        result.created_count += 1
