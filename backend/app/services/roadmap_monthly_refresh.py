from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import StudyRoadmap, StudentSubject
from app.services.planning import PlanningService


@dataclass(frozen=True)
class MonthlyTacticalRefreshResult:
    students_processed: int
    students_refreshed: int
    target_date: date


class RoadmapMonthlyRefreshService:
    """Enqueue tactical-layer refresh for students with an active study roadmap."""

    def run(self, db: Session, *, today: date | None = None) -> MonthlyTacticalRefreshResult:
        day = today or date.today()
        student_ids = list(
            db.execute(
                select(StudyRoadmap.student_user_id).where(
                    StudyRoadmap.status == "active",
                    StudyRoadmap.current_version_id.is_not(None),
                )
            )
            .scalars()
            .all()
        )
        refreshed = 0
        planner = PlanningService()
        for student_user_id in student_ids:
            has_subjects = db.execute(
                select(StudentSubject.id).where(
                    StudentSubject.student_user_id == student_user_id,
                    StudentSubject.enabled.is_(True),
                )
            ).first()
            if has_subjects is None:
                continue
            if planner.refresh_tactical_from_roadmap(db, student_user_id, today=day):
                refreshed += 1
        return MonthlyTacticalRefreshResult(
            students_processed=len(student_ids),
            students_refreshed=refreshed,
            target_date=day,
        )
