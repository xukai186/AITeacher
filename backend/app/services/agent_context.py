from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.services.report import ReportQuery, ReportService


@dataclass(frozen=True)
class SubjectContext:
    student_user_id: uuid.UUID
    subject_code: str
    wrong_source_counts: dict[str, int]
    weak_node_count: int
    recommendation_count: int
    recommendations: list[dict]


def get_subject_context(
    db: Session,
    *,
    student_user_id: uuid.UUID,
    subject_code: str,
) -> SubjectContext:
    overview = ReportService.overview(
        db,
        ReportQuery(student_user_id=student_user_id, subject_code=subject_code),
    )
    return SubjectContext(
        student_user_id=student_user_id,
        subject_code=subject_code,
        wrong_source_counts=overview.wrong_source_counts,
        weak_node_count=len(overview.weak_nodes),
        recommendation_count=len(overview.recommendations),
        recommendations=overview.recommendations,
    )
