from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import SelfTestGrade, SelfTestPaper, SelfTestSubmission, WrongBookItem
from app.schemas.report import ReportOverviewOut, ReportTrendPointOut, ReportWeakNodeOut


@dataclass(frozen=True)
class ReportQuery:
    student_user_id: uuid.UUID
    subject_code: str | None = None
    trend_limit: int = 10
    weak_nodes_limit: int = 5


class ReportService:
    @staticmethod
    def overview(db: Session, q: ReportQuery) -> ReportOverviewOut:
        source_counts_stmt = (
            select(WrongBookItem.source_type, func.count(WrongBookItem.id))
            .where(WrongBookItem.student_user_id == q.student_user_id)
            .group_by(WrongBookItem.source_type)
        )
        if q.subject_code:
            source_counts_stmt = source_counts_stmt.where(WrongBookItem.subject_code == q.subject_code)
        source_counts = {k: int(v) for k, v in db.execute(source_counts_stmt).all()}

        weak_stmt = (
            select(WrongBookItem.knowledge_node_id, func.count(WrongBookItem.id))
            .where(WrongBookItem.student_user_id == q.student_user_id)
            .group_by(WrongBookItem.knowledge_node_id)
            .order_by(func.count(WrongBookItem.id).desc())
            .limit(q.weak_nodes_limit)
        )
        if q.subject_code:
            weak_stmt = weak_stmt.where(WrongBookItem.subject_code == q.subject_code)
        weak_nodes = [
            ReportWeakNodeOut(
                knowledge_node_id=node_id,
                wrong_count=int(cnt),
                total_count=int(cnt),
            )
            for node_id, cnt in db.execute(weak_stmt).all()
        ]

        trend_stmt = (
            select(
                SelfTestGrade.submission_id,
                SelfTestSubmission.paper_id,
                SelfTestPaper.subject_code,
                SelfTestGrade.total_score,
                SelfTestSubmission.created_at,
            )
            .join(SelfTestSubmission, SelfTestSubmission.id == SelfTestGrade.submission_id)
            .join(SelfTestPaper, SelfTestPaper.id == SelfTestSubmission.paper_id)
            .where(SelfTestSubmission.student_user_id == q.student_user_id)
            .order_by(SelfTestSubmission.created_at.desc())
            .limit(q.trend_limit)
        )
        if q.subject_code:
            trend_stmt = trend_stmt.where(SelfTestPaper.subject_code == q.subject_code)
        trend = [
            ReportTrendPointOut(
                submission_id=sub_id,
                paper_id=paper_id,
                subject_code=subject_code,
                total_score=int(total_score),
                created_at=created_at,
            )
            for sub_id, paper_id, subject_code, total_score, created_at in db.execute(trend_stmt).all()
        ]

        return ReportOverviewOut(
            subject_code=q.subject_code,
            wrong_source_counts=source_counts,
            weak_nodes=weak_nodes,
            self_test_trend=trend,
        )

