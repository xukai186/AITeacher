from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import StudyRoadmap, StudyRoadmapVersion


@dataclass(frozen=True)
class MonthSlice:
    month: str
    label: str
    subjects: dict[str, dict]
    milestones: list[str]


class RoadmapContextService:
    def current_month_slice(
        self, db: Session, *, student_user_id: uuid.UUID, today: date | None = None
    ) -> MonthSlice | None:
        day = today or date.today()
        month_key = day.strftime("%Y-%m")
        roadmap = db.execute(
            select(StudyRoadmap).where(StudyRoadmap.student_user_id == student_user_id)
        ).scalar_one_or_none()
        if roadmap is None or roadmap.current_version_id is None:
            return None
        version = db.get(StudyRoadmapVersion, roadmap.current_version_id)
        if version is None or not version.months_json:
            return None
        months = version.months_json.get("months") or []
        for item in months:
            if not isinstance(item, dict):
                continue
            if str(item.get("month")) != month_key:
                continue
            subjects = item.get("subjects") or {}
            if not isinstance(subjects, dict):
                subjects = {}
            milestones = item.get("milestones") or []
            return MonthSlice(
                month=month_key,
                label=str(item.get("label") or month_key),
                subjects=subjects,
                milestones=[str(m) for m in milestones if m],
            )
        if months and isinstance(months[0], dict):
            item = months[0]
            subjects = item.get("subjects") or {}
            if not isinstance(subjects, dict):
                subjects = {}
            return MonthSlice(
                month=str(item.get("month") or month_key),
                label=str(item.get("label") or month_key),
                subjects=subjects,
                milestones=[str(m) for m in (item.get("milestones") or []) if m],
            )
        return None
