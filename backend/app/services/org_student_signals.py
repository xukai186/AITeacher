from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import DailyTask, MasterPlan, PlanReviewJob, WrongBookItem


@dataclass
class OrgStudentSignals:
    pending_task_count: int = 0
    open_review_job_count: int = 0
    requires_plan_confirmation: bool = False
    wrong_added_7d: int = 0


def signals_for_students(
    db: Session, student_ids: list[uuid.UUID]
) -> dict[uuid.UUID, OrgStudentSignals]:
    if not student_ids:
        return {}

    out = {sid: OrgStudentSignals() for sid in student_ids}
    today = date.today()
    since = datetime.now(timezone.utc) - timedelta(days=7)

    for sid, cnt in db.execute(
        select(DailyTask.student_user_id, func.count(DailyTask.id))
        .where(
            DailyTask.student_user_id.in_(student_ids),
            DailyTask.date == today,
            DailyTask.status == "pending",
        )
        .group_by(DailyTask.student_user_id)
    ).all():
        out[sid].pending_task_count = int(cnt)

    for sid, cnt in db.execute(
        select(PlanReviewJob.student_user_id, func.count(PlanReviewJob.id))
        .where(
            PlanReviewJob.student_user_id.in_(student_ids),
            PlanReviewJob.status.in_(("pending", "retry", "running")),
        )
        .group_by(PlanReviewJob.student_user_id)
    ).all():
        out[sid].open_review_job_count = int(cnt)

    for sid in db.execute(
        select(MasterPlan.student_user_id).where(
            MasterPlan.student_user_id.in_(student_ids),
            MasterPlan.pending_version_id.is_not(None),
        )
    ).scalars():
        out[sid].requires_plan_confirmation = True

    for sid, cnt in db.execute(
        select(WrongBookItem.student_user_id, func.count(WrongBookItem.id))
        .where(
            WrongBookItem.student_user_id.in_(student_ids),
            WrongBookItem.created_at >= since,
        )
        .group_by(WrongBookItem.student_user_id)
    ).all():
        out[sid].wrong_added_7d = int(cnt)

    return out
