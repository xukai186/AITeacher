from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyTask
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
        day = target_date or (date.today() + timedelta(days=1))
        overview = ReportService.overview(
            db,
            ReportQuery(student_user_id=student_user_id, subject_code=subject_code),
        )
        result = ApplyRecommendationsResult(target_date=day, subject_code=subject_code)

        for rec in overview.recommendations:
            rec_type = str(rec.get("type") or "study")
            title = str(rec.get("title") or "学习任务")
            rec_subject = rec.get("subject_code") or subject_code
            if rec_subject != subject_code:
                continue

            knowledge_node_id = rec.get("knowledge_node_id")
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
                continue

            task = DailyTask(
                student_user_id=student_user_id,
                date=day,
                subject_code=subject_code,
                type=rec_type,
                ref_id=ref_id,
                status="pending",
                est_minutes=REC_EST_MINUTES.get(rec_type, 30),
                title=title,
                payload_json={
                    "source": "report_recommendation",
                    "recommendation_type": rec_type,
                    "detail": rec.get("detail"),
                    "knowledge_node_id": knowledge_node_id,
                },
            )
            db.add(task)
            db.flush()
            result.created.append(task)
            result.created_count += 1

        result.budget_minutes = budget_minutes_for_date(db, student_user_id, day)
        result.scheduled_minutes = scheduled_minutes_for_date(db, student_user_id, day)
        if result.budget_minutes is not None and result.scheduled_minutes > result.budget_minutes:
            result.over_budget = True
            result.warnings.append(
                f"当日已排 {result.scheduled_minutes} 分钟，超过总规划预算 {result.budget_minutes} 分钟；"
                "总规划 Agent 后续可协调削减低优先级任务。"
            )

        return result
