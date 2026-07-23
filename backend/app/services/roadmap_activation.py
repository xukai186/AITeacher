from __future__ import annotations

import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RoadmapGenerationJob, StudyRoadmap, StudyRoadmapVersion
from app.services.planning import PlanningService
from app.services.roadmap_resolve import validate_months_leaf_ids
from app.services.tasks import TaskGenerator


class RoadmapActivationService:
    def get_or_create_roadmap(self, db: Session, *, student_user_id: uuid.UUID) -> StudyRoadmap:
        roadmap = db.execute(
            select(StudyRoadmap).where(StudyRoadmap.student_user_id == student_user_id)
        ).scalar_one_or_none()
        if roadmap is None:
            roadmap = StudyRoadmap(student_user_id=student_user_id, status="draft")
            db.add(roadmap)
            db.flush()
        return roadmap

    def attach_pending_version(
        self,
        db: Session,
        *,
        student_user_id: uuid.UUID,
        version: StudyRoadmapVersion,
    ) -> StudyRoadmap:
        roadmap = self.get_or_create_roadmap(db, student_user_id=student_user_id)
        if roadmap.pending_version_id:
            old = db.get(StudyRoadmapVersion, roadmap.pending_version_id)
            if old is not None:
                db.delete(old)
                db.flush()
        roadmap.pending_version_id = version.id
        roadmap.status = "draft"
        db.flush()
        return roadmap

    def get_state(self, db: Session, *, student_user_id: uuid.UUID) -> dict:
        roadmap = db.execute(
            select(StudyRoadmap).where(StudyRoadmap.student_user_id == student_user_id)
        ).scalar_one_or_none()
        job = db.execute(
            select(RoadmapGenerationJob)
            .where(RoadmapGenerationJob.student_user_id == student_user_id)
            .order_by(RoadmapGenerationJob.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if roadmap is None:
            return {
                "roadmap_id": None,
                "status": None,
                "active_version": None,
                "pending_version": None,
                "generation_job": self._job_dict(job),
            }
        active = (
            db.get(StudyRoadmapVersion, roadmap.current_version_id)
            if roadmap.current_version_id
            else None
        )
        pending = (
            db.get(StudyRoadmapVersion, roadmap.pending_version_id)
            if roadmap.pending_version_id
            else None
        )
        return {
            "roadmap_id": roadmap.id,
            "status": roadmap.status,
            "active_version": active,
            "pending_version": pending,
            "generation_job": self._job_dict(job),
        }

    @staticmethod
    def _job_dict(job: RoadmapGenerationJob | None) -> dict | None:
        if job is None:
            return None
        return {
            "id": str(job.id),
            "status": job.status,
            "error_message": job.error_message,
            "roadmap_version_id": str(job.roadmap_version_id) if job.roadmap_version_id else None,
        }

    def confirm_pending(self, db: Session, *, student_user_id: uuid.UUID) -> StudyRoadmapVersion:
        roadmap = db.execute(
            select(StudyRoadmap).where(StudyRoadmap.student_user_id == student_user_id)
        ).scalar_one_or_none()
        if roadmap is None or roadmap.pending_version_id is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "no pending roadmap to confirm")
        pending = db.get(StudyRoadmapVersion, roadmap.pending_version_id)
        if pending is None:
            roadmap.pending_version_id = None
            raise HTTPException(status.HTTP_404_NOT_FOUND, "pending roadmap version missing")
        bad = validate_months_leaf_ids(db, pending.months_json)
        if bad:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "路线图含无效考纲节点")
        roadmap.current_version_id = pending.id
        roadmap.pending_version_id = None
        roadmap.status = "active"
        db.flush()
        PlanningService().create_initial_plans(db, student_user_id)
        TaskGenerator().generate_next_7_days(db, student_user_id=student_user_id, today=date.today())
        db.flush()
        return pending

    def reject_pending(self, db: Session, *, student_user_id: uuid.UUID) -> None:
        roadmap = db.execute(
            select(StudyRoadmap).where(StudyRoadmap.student_user_id == student_user_id)
        ).scalar_one_or_none()
        if roadmap is None or roadmap.pending_version_id is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "no pending roadmap to reject")
        pending = db.get(StudyRoadmapVersion, roadmap.pending_version_id)
        roadmap.pending_version_id = None
        if pending is not None:
            db.delete(pending)
        db.flush()
