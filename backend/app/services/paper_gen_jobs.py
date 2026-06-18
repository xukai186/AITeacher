from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.orm import Session

from app.models import PaperGenJob, PlacementPaper, PlacementQuestion, SelfTestPaper, SelfTestQuestion, User
from app.services.paper_gen import DEFAULT_QUESTION_COUNT, PaperGenService, PaperPurpose
from app.services.placement_paper_context import resolve_placement_question_count

ProgressCallback = Callable[[int, int, str], None]


@dataclass(frozen=True)
class EnqueuePaperGenResult:
    job_id: uuid.UUID
    created: bool


class PaperGenJobService:
    def get_active_for_paper(
        self,
        db: Session,
        *,
        paper_id: uuid.UUID,
        purpose: str,
    ) -> PaperGenJob | None:
        return db.execute(
            select(PaperGenJob).where(
                PaperGenJob.paper_id == paper_id,
                PaperGenJob.purpose == purpose,
                PaperGenJob.status.in_(("pending", "running", "retry")),
            )
        ).scalar_one_or_none()

    def enqueue(
        self,
        db: Session,
        *,
        student_user_id: uuid.UUID,
        subject_code: str,
        purpose: str,
        paper_id: uuid.UUID,
    ) -> EnqueuePaperGenResult:
        existing = self.get_active_for_paper(db, paper_id=paper_id, purpose=purpose)
        if existing is not None:
            return EnqueuePaperGenResult(job_id=existing.id, created=False)

        total = DEFAULT_QUESTION_COUNT
        if purpose == "placement":
            total = resolve_placement_question_count(
                db, subject_code=subject_code, student_user_id=student_user_id
            )

        job = PaperGenJob(
            student_user_id=student_user_id,
            subject_code=subject_code,
            purpose=purpose,
            paper_id=paper_id,
            status="pending",
            attempts=0,
            max_attempts=3,
            run_after=datetime.now(timezone.utc),
            progress_json={
                "done": 0,
                "total": total,
                "message": "等待生成…",
            },
        )
        db.add(job)
        db.flush()
        return EnqueuePaperGenResult(job_id=job.id, created=True)

    def get_for_student(
        self,
        db: Session,
        *,
        job_id: uuid.UUID,
        student_user_id: uuid.UUID,
    ) -> PaperGenJob | None:
        job = db.get(PaperGenJob, job_id)
        if job is None or job.student_user_id != student_user_id:
            return None
        return job


class PaperGenJobRunner:
    def __init__(self, paper_gen: PaperGenService | None = None) -> None:
        self._paper_gen = paper_gen or PaperGenService()

    def run_pending(
        self,
        db: Session,
        *,
        limit: int = 50,
        job_id: uuid.UUID | None = None,
        lock_timeout_seconds: int = 60 * 15,
    ) -> int:
        now = datetime.now(timezone.utc)
        lock_cutoff = now - timedelta(seconds=lock_timeout_seconds)

        filters = [
            PaperGenJob.status.in_(("pending", "retry")),
            PaperGenJob.run_after <= now,
            or_(PaperGenJob.locked_at.is_(None), PaperGenJob.locked_at < lock_cutoff),
            PaperGenJob.attempts < PaperGenJob.max_attempts,
        ]
        if job_id is not None:
            filters.append(PaperGenJob.id == job_id)

        jobs = db.execute(
            select(PaperGenJob)
            .where(and_(*filters))
            .order_by(PaperGenJob.run_after.asc(), PaperGenJob.created_at.asc())
            .limit(limit)
        ).scalars().all()
        if not jobs:
            return 0

        ran = 0
        for job in jobs:
            self._run_one(db, job, now)
            ran += 1
        return ran

    def _run_one(self, db: Session, job: PaperGenJob, now: datetime) -> None:
        db.execute(
            update(PaperGenJob)
            .where(PaperGenJob.id == job.id)
            .values(status="running", locked_at=now)
        )
        db.flush()
        db.refresh(job)

        try:
            generated_count = self._execute_job(db, job)
            db.execute(
                update(PaperGenJob)
                .where(PaperGenJob.id == job.id)
                .values(
                    status="succeeded",
                    locked_at=None,
                    attempts=job.attempts + 1,
                    last_error=None,
                    progress_json={
                        "done": generated_count,
                        "total": generated_count,
                        "message": "题目生成完成",
                    },
                    result_json={"paper_id": str(job.paper_id)},
                )
            )
        except Exception as exc:  # noqa: BLE001
            next_attempt = job.attempts + 1
            failed = next_attempt >= job.max_attempts
            db.execute(
                update(PaperGenJob)
                .where(PaperGenJob.id == job.id)
                .values(
                    status="failed" if failed else "retry",
                    locked_at=None,
                    attempts=next_attempt,
                    last_error=str(exc),
                    run_after=now + timedelta(seconds=15),
                )
            )
            self._mark_paper_failed(db, job)
        db.flush()

    def _execute_job(self, db: Session, job: PaperGenJob) -> int:
        student = db.get(User, job.student_user_id)
        if student is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "student not found")

        total = DEFAULT_QUESTION_COUNT
        if job.purpose == "placement":
            total = resolve_placement_question_count(
                db, subject_code=job.subject_code, student_user_id=job.student_user_id
            )

        def on_progress(done: int, total_batches: int, message: str) -> None:
            db.execute(
                update(PaperGenJob)
                .where(PaperGenJob.id == job.id)
                .values(
                    progress_json={
                        "done": done,
                        "total": total_batches,
                        "message": message,
                    }
                )
            )
            db.flush()

        if job.purpose == "placement":
            paper = db.get(PlacementPaper, job.paper_id)
            if paper is None:
                raise ValueError("placement paper not found")
            db.execute(delete(PlacementQuestion).where(PlacementQuestion.paper_id == paper.id))
            db.flush()
            generated = self._paper_gen.generate_for_placement(
                db,
                org_id=student.org_id,
                student_user_id=job.student_user_id,
                subject_code=job.subject_code,
                question_count=None,
                on_progress=on_progress,
            )
            if not generated:
                raise ValueError("Failed to generate placement questions")
            for q in generated:
                db.add(
                    PlacementQuestion(
                        paper_id=paper.id,
                        seq=q.seq,
                        knowledge_node_id=q.knowledge_node_id,
                        q_type=q.q_type,
                        stem=q.stem,
                        choices_json=q.choices_json,
                        answer_key=q.answer_key,
                        points=q.points,
                    )
                )
            paper.status = "ready"
            return len(generated)

        if job.purpose == "self_test":
            paper = db.get(SelfTestPaper, job.paper_id)
            if paper is None:
                raise ValueError("self-test paper not found")
            generated = self._paper_gen.generate_for_self_test(
                db,
                org_id=student.org_id,
                student_user_id=job.student_user_id,
                subject_code=job.subject_code,
                question_count=total,
                on_progress=on_progress,
            )
            if not generated:
                raise ValueError("Failed to generate self-test questions")
            for q in generated:
                db.add(
                    SelfTestQuestion(
                        paper_id=paper.id,
                        seq=q.seq,
                        knowledge_node_id=q.knowledge_node_id,
                        q_type=q.q_type,
                        stem=q.stem,
                        choices_json=q.choices_json,
                        answer_key=q.answer_key,
                        points=q.points,
                        rubric_json=None,
                    )
                )
            paper.status = "ready"
            return len(generated)

        raise ValueError(f"unsupported paper gen purpose: {job.purpose}")

    @staticmethod
    def _mark_paper_failed(db: Session, job: PaperGenJob) -> None:
        if job.purpose == "placement":
            paper = db.get(PlacementPaper, job.paper_id)
            if paper is not None:
                paper.status = "failed"
        elif job.purpose == "self_test":
            paper = db.get(SelfTestPaper, job.paper_id)
            if paper is not None:
                paper.status = "failed"


def kick_paper_gen_job(job_id: uuid.UUID) -> None:
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        PaperGenJobRunner().run_pending(db, limit=1, job_id=job_id)
        db.commit()
    finally:
        db.close()


def run_paper_gen_job_if_needed(db: Session, job_id: uuid.UUID | None) -> None:
    if job_id is not None:
        PaperGenJobRunner().run_pending(db, limit=1, job_id=job_id)
