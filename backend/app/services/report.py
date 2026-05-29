from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import SelfTestGrade, SelfTestPaper, SelfTestSubmission, SyllabusNode, WrongBookItem
from app.schemas.report import ReportOverviewOut, ReportTrendPointOut, ReportWeakNodeOut


@dataclass(frozen=True)
class ReportQuery:
    student_user_id: uuid.UUID
    subject_code: str | None = None
    trend_limit: int = 10
    weak_nodes_limit: int = 5


class ReportService:
    @staticmethod
    def _last_7d(db: Session, q: ReportQuery) -> dict:
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)

        wb_stmt = select(WrongBookItem).where(
            WrongBookItem.student_user_id == q.student_user_id,
            WrongBookItem.created_at >= cutoff,
        )
        if q.subject_code:
            wb_stmt = wb_stmt.where(WrongBookItem.subject_code == q.subject_code)
        wrong_added = db.execute(wb_stmt).scalars().all()

        wb_source_stmt = (
            select(WrongBookItem.source_type, func.count(WrongBookItem.id))
            .where(
                WrongBookItem.student_user_id == q.student_user_id,
                WrongBookItem.created_at >= cutoff,
            )
            .group_by(WrongBookItem.source_type)
        )
        if q.subject_code:
            wb_source_stmt = wb_source_stmt.where(WrongBookItem.subject_code == q.subject_code)
        wrong_source_counts = {k: int(v) for k, v in db.execute(wb_source_stmt).all()}

        st_stmt = (
            select(SelfTestGrade.total_score)
            .join(SelfTestSubmission, SelfTestSubmission.id == SelfTestGrade.submission_id)
            .join(SelfTestPaper, SelfTestPaper.id == SelfTestSubmission.paper_id)
            .where(
                SelfTestSubmission.student_user_id == q.student_user_id,
                SelfTestSubmission.created_at >= cutoff,
            )
        )
        if q.subject_code:
            st_stmt = st_stmt.where(SelfTestPaper.subject_code == q.subject_code)
        scores = [int(s) for (s,) in db.execute(st_stmt).all()]
        self_test_count = len(scores)
        self_test_avg_score = (sum(scores) / self_test_count) if self_test_count else None

        return {
            "wrong_added": len(wrong_added),
            "wrong_source_counts": wrong_source_counts,
            "self_test_count": self_test_count,
            "self_test_avg_score": self_test_avg_score,
        }

    @staticmethod
    def _recommendations(
        q: ReportQuery,
        source_counts: dict[str, int],
        weak_nodes: list[ReportWeakNodeOut],
        trend: list[ReportTrendPointOut],
    ) -> list[dict]:
        recs: list[dict] = []

        top = weak_nodes[0] if weak_nodes else None
        if top is not None:
            name = top.knowledge_node_name or "未标注知识点"
            recs.append(
                {
                    "type": "review_wrong",
                    "title": f"优先复习：{name}",
                    "detail": f"该知识点近期错题较多（{top.wrong_count}）。建议先把对应错题重做一轮，再做一次同主题自测巩固。",
                    "subject_code": q.subject_code,
                    "knowledge_node_id": str(top.knowledge_node_id) if top.knowledge_node_id else None,
                }
            )

        if source_counts.get("self_test", 0) > 0:
            recs.append(
                {
                    "type": "self_test",
                    "title": "安排一次自测检验",
                    "detail": "完成错题复习后，建议生成一份自测卷进行检验，关注薄弱点是否改善。",
                    "subject_code": q.subject_code,
                    "knowledge_node_id": None,
                }
            )

        if trend:
            last = trend[0]
            recs.append(
                {
                    "type": "check_result",
                    "title": "回看最近一次自测解析",
                    "detail": f"最近一次自测得分 {last.total_score}，建议回看错误题的解析与评分反馈，明确丢分原因。",
                    "subject_code": q.subject_code,
                    "knowledge_node_id": None,
                }
            )

        return recs[:3]

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
            select(WrongBookItem.knowledge_node_id, SyllabusNode.name, func.count(WrongBookItem.id))
            .where(WrongBookItem.student_user_id == q.student_user_id)
            .outerjoin(SyllabusNode, SyllabusNode.id == WrongBookItem.knowledge_node_id)
            .group_by(WrongBookItem.knowledge_node_id)
            .group_by(SyllabusNode.name)
            .order_by(func.count(WrongBookItem.id).desc())
            .limit(q.weak_nodes_limit)
        )
        if q.subject_code:
            weak_stmt = weak_stmt.where(WrongBookItem.subject_code == q.subject_code)
        weak_nodes = [
            ReportWeakNodeOut(
                knowledge_node_id=node_id,
                knowledge_node_name=node_name,
                wrong_count=int(cnt),
                total_count=int(cnt),
            )
            for node_id, node_name, cnt in db.execute(weak_stmt).all()
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
            recommendations=ReportService._recommendations(q, source_counts, weak_nodes, trend),
            last_7d=ReportService._last_7d(db, q),
        )

