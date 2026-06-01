from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SelfTestGrade, SelfTestPaper, SelfTestSubmission

MIN_DAYS_SINCE_LAST_GRADED = 5
MAX_SELF_TESTS_PER_WEEK = 2


@dataclass
class SelfTestEligibility:
    allowed: bool
    reasons: list[str] = field(default_factory=list)


class SelfTestEligibilityService:
    """自测组卷硬规则（规格 §6.4 MVP）。"""

    def check(
        self,
        db: Session,
        *,
        student_user_id: uuid.UUID,
        subject_code: str,
        as_of: date | None = None,
    ) -> SelfTestEligibility:
        today = as_of or date.today()
        reasons: list[str] = []

        locked = db.execute(
            select(SelfTestPaper.id).where(
                SelfTestPaper.student_user_id == student_user_id,
                SelfTestPaper.subject_code == subject_code,
                SelfTestPaper.status == "locked",
            )
        ).first()
        if locked is not None:
            reasons.append("机构已锁定本科试卷，暂不可生成新自测")

        submitted_ids = select(SelfTestSubmission.paper_id).where(
            SelfTestSubmission.student_user_id == student_user_id
        )
        in_progress = db.execute(
            select(SelfTestPaper.id).where(
                SelfTestPaper.student_user_id == student_user_id,
                SelfTestPaper.subject_code == subject_code,
                SelfTestPaper.status == "ready",
                SelfTestPaper.id.not_in(submitted_ids),
            )
        ).first()
        if in_progress is not None:
            reasons.append("存在未提交的自测卷，请先完成或放弃后再生成")

        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=7)
        week_count = db.execute(
            select(SelfTestSubmission.id)
            .join(SelfTestPaper, SelfTestPaper.id == SelfTestSubmission.paper_id)
            .join(SelfTestGrade, SelfTestGrade.submission_id == SelfTestSubmission.id)
            .where(
                SelfTestSubmission.student_user_id == student_user_id,
                SelfTestPaper.subject_code == subject_code,
                SelfTestSubmission.submitted_at >= datetime.combine(
                    week_start, datetime.min.time(), tzinfo=timezone.utc
                ),
                SelfTestSubmission.submitted_at < datetime.combine(
                    week_end, datetime.min.time(), tzinfo=timezone.utc
                ),
            )
        ).all()
        if len(week_count) >= MAX_SELF_TESTS_PER_WEEK:
            reasons.append(f"本周本科自测已达 {MAX_SELF_TESTS_PER_WEEK} 次上限")

        last_graded_at = db.execute(
            select(SelfTestSubmission.submitted_at)
            .join(SelfTestPaper, SelfTestPaper.id == SelfTestSubmission.paper_id)
            .join(SelfTestGrade, SelfTestGrade.submission_id == SelfTestSubmission.id)
            .where(
                SelfTestSubmission.student_user_id == student_user_id,
                SelfTestPaper.subject_code == subject_code,
                SelfTestSubmission.submitted_at.is_not(None),
            )
            .order_by(SelfTestSubmission.submitted_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        if last_graded_at is not None:
            last_day = last_graded_at.date() if hasattr(last_graded_at, "date") else last_graded_at
            days_since = (today - last_day).days
            if days_since < MIN_DAYS_SINCE_LAST_GRADED:
                reasons.append(
                    f"距上次自测仅 {days_since} 天，需间隔至少 {MIN_DAYS_SINCE_LAST_GRADED} 天"
                )

        return SelfTestEligibility(allowed=len(reasons) == 0, reasons=reasons)
