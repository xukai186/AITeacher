from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RoadmapGenerationJob, StudyRoadmap, StudyRoadmapVersion
from app.services.roadmap_activation import RoadmapActivationService
from app.services.roadmap_draft import RoadmapDraftService


@dataclass(frozen=True)
class EnqueueRoadmapResult:
    job_id: uuid.UUID
    created: bool


class RoadmapGenerationJobService:
    def get_active(self, db: Session, *, student_user_id: uuid.UUID) -> RoadmapGenerationJob | None:
        return db.execute(
            select(RoadmapGenerationJob).where(
                RoadmapGenerationJob.student_user_id == student_user_id,
                RoadmapGenerationJob.status.in_(("pending", "running")),
            )
        ).scalar_one_or_none()

    def enqueue(self, db: Session, *, student_user_id: uuid.UUID) -> EnqueueRoadmapResult:
        existing = self.get_active(db, student_user_id=student_user_id)
        if existing is not None:
            return EnqueueRoadmapResult(job_id=existing.id, created=False)
        job = RoadmapGenerationJob(student_user_id=student_user_id, status="pending")
        db.add(job)
        db.flush()
        return EnqueueRoadmapResult(job_id=job.id, created=True)

    def run_job(self, db: Session, job_id: uuid.UUID) -> None:
        job = db.get(RoadmapGenerationJob, job_id)
        if job is None or job.status not in ("pending", "running"):
            return
        job.status = "running"
        db.flush()
        try:
            draft = RoadmapDraftService().draft(db, student_user_id=job.student_user_id)
            roadmap = RoadmapActivationService().get_or_create_roadmap(
                db, student_user_id=job.student_user_id
            )
            latest = db.execute(
                select(StudyRoadmapVersion)
                .where(StudyRoadmapVersion.roadmap_id == roadmap.id)
                .order_by(StudyRoadmapVersion.version.desc())
                .limit(1)
            ).scalar_one_or_none()
            next_ver = (latest.version + 1) if latest is not None else 1
            version = StudyRoadmapVersion(
                roadmap_id=roadmap.id,
                version=next_ver,
                source=draft.source,
                start_date=draft.start_date,
                end_date=draft.end_date,
                summary_json=draft.summary_json,
                months_json=draft.months_json,
            )
            db.add(version)
            db.flush()
            RoadmapActivationService().attach_pending_version(
                db, student_user_id=job.student_user_id, version=version
            )
            job.status = "succeeded"
            job.roadmap_version_id = version.id
            job.error_message = None
            job.finished_at = datetime.now(timezone.utc)
        except Exception as exc:
            job.status = "failed"
            job.error_message = str(exc)[:1000]
            job.finished_at = datetime.now(timezone.utc)
        db.flush()


def run_roadmap_job_if_needed(db: Session, job_id: uuid.UUID) -> None:
    RoadmapGenerationJobService().run_job(db, job_id)


class RoadmapGenerationJobRunner:
    """Poll pending roadmap generation jobs (CLI worker)."""

    def run_pending(
        self,
        db: Session,
        *,
        limit: int = 20,
        job_id: uuid.UUID | None = None,
    ) -> int:
        svc = RoadmapGenerationJobService()
        if job_id is not None:
            job = db.get(RoadmapGenerationJob, job_id)
            if job is None or job.status not in ("pending", "running"):
                return 0
            svc.run_job(db, job_id)
            return 1

        jobs = list(
            db.execute(
                select(RoadmapGenerationJob)
                .where(RoadmapGenerationJob.status == "pending")
                .order_by(RoadmapGenerationJob.created_at.asc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
        for job in jobs:
            svc.run_job(db, job.id)
        return len(jobs)


def kick_roadmap_job(job_id: uuid.UUID) -> None:
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        run_roadmap_job_if_needed(db, job_id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
