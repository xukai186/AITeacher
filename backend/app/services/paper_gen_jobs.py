from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.orm import Session

from app.models import PaperGenJob, PlacementPaper, PlacementQuestion, SelfTestPaper, SelfTestQuestion, User
from app.services.paper_gen import DEFAULT_QUESTION_COUNT, PaperGenService
from app.services.placement_paper_context import (
    build_placement_context,
    build_placement_slots,
    leaf_nodes_for_placement,
    materialize_placement_slots,
    materialize_syllabus_nodes,
    resolve_placement_question_count,
)
from app.services.report import ReportQuery, ReportService

ProgressCallback = Callable[[int, int, str], None]

STALE_RUNNING_SECONDS = 90
_kick_threads: dict[uuid.UUID, threading.Thread] = {}
_kick_lock = threading.Lock()


def is_stale_running(job: PaperGenJob, *, now: datetime | None = None) -> bool:
    if job.status != "running":
        return False
    if job.locked_at is None:
        return True
    current = now or datetime.now(timezone.utc)
    lock_cutoff = current - timedelta(seconds=STALE_RUNNING_SECONDS)
    return job.locked_at < lock_cutoff


def should_kick_paper_gen_job(job: PaperGenJob, *, now: datetime | None = None) -> bool:
    if job.status in ("pending", "retry"):
        return True
    if is_stale_running(job, now=now):
        return True
    return False


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

    def get_for_paper(
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

        prior = self.get_for_paper(db, paper_id=paper_id, purpose=purpose)
        if prior is not None:
            prior.student_user_id = student_user_id
            prior.subject_code = subject_code
            prior.status = "pending"
            prior.attempts = 0
            prior.max_attempts = 3
            prior.run_after = datetime.now(timezone.utc)
            prior.locked_at = None
            prior.last_error = None
            prior.result_json = None
            prior.progress_json = {
                "done": 0,
                "total": total,
                "message": "等待生成…",
            }
            db.flush()
            return EnqueuePaperGenResult(job_id=prior.id, created=False)

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

        if job_id is not None:
            job = db.get(PaperGenJob, job_id)
            jobs: list[PaperGenJob] = []
            if job is not None and job.attempts < job.max_attempts and job.run_after <= now:
                if job.status in ("pending", "retry"):
                    jobs = [job]
                elif is_stale_running(job, now=now):
                    db.execute(
                        update(PaperGenJob)
                        .where(PaperGenJob.id == job.id)
                        .values(status="retry", locked_at=None)
                    )
                    db.flush()
                    db.refresh(job)
                    jobs = [job]
        else:
            filters = [
                PaperGenJob.status.in_(("pending", "retry")),
                PaperGenJob.run_after <= now,
                or_(PaperGenJob.locked_at.is_(None), PaperGenJob.locked_at < lock_cutoff),
                PaperGenJob.attempts < PaperGenJob.max_attempts,
            ]
            jobs = list(
                db.execute(
                    select(PaperGenJob)
                    .where(and_(*filters))
                    .order_by(PaperGenJob.run_after.asc(), PaperGenJob.created_at.asc())
                    .limit(limit)
                )
                .scalars()
                .all()
            )
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
        db.commit()

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
            db.commit()
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
            self._mark_paper_failed(db, job.purpose, job.paper_id)
            db.commit()

    def _execute_job(self, db: Session, job: PaperGenJob) -> int:
        student = db.get(User, job.student_user_id)
        if student is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "student not found")

        policy = self._paper_gen._policy(db, student.org_id)
        provider = policy.provider if policy is not None else None
        model = policy.model if policy is not None else None
        params = dict(policy.params or {}) if policy is not None else {}
        on_progress = self._make_progress_callback(job.id)

        total = DEFAULT_QUESTION_COUNT
        if job.purpose == "placement":
            paper = db.get(PlacementPaper, job.paper_id)
            if paper is None:
                raise ValueError("placement paper not found")
            db.execute(delete(PlacementQuestion).where(PlacementQuestion.paper_id == paper.id))
            overview = ReportService.overview(
                db,
                ReportQuery(
                    student_user_id=job.student_user_id,
                    subject_code=job.subject_code,
                ),
            )
            placement_context = build_placement_context(
                db,
                student_user_id=job.student_user_id,
                subject_code=job.subject_code,
            )
            leaves = leaf_nodes_for_placement(
                db,
                subject_code=job.subject_code,
                exam_year=placement_context.exam_year,
            )
            if not leaves:
                raise ValueError("syllabus missing for subject")
            placement_slots = materialize_placement_slots(
                build_placement_slots(
                    db, placement_context, leaves, overview.weak_nodes
                )
            )
            db.commit()
            generated = self._paper_gen.generate_prepared_placement(
                provider=provider,
                model=model,
                params=params,
                placement_context=placement_context,
                placement_slots=placement_slots,
                student_user_id=job.student_user_id,
                subject_code=job.subject_code,
                on_progress=on_progress,
            )
            if not generated:
                raise ValueError("Failed to generate placement questions")
            paper = db.get(PlacementPaper, job.paper_id)
            if paper is None:
                raise ValueError("placement paper not found")
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
                        rubric_json=q.rubric_json,
                    )
                )
            paper.status = "ready"
            db.flush()
            return len(generated)

        if job.purpose == "self_test":
            paper = db.get(SelfTestPaper, job.paper_id)
            if paper is None:
                raise ValueError("self-test paper not found")
            overview = ReportService.overview(
                db,
                ReportQuery(
                    student_user_id=job.student_user_id,
                    subject_code=job.subject_code,
                ),
            )
            leaves = self._paper_gen._leaf_nodes(db, job.subject_code)
            if not leaves:
                raise ValueError("syllabus missing for subject")
            target_nodes = materialize_syllabus_nodes(
                self._paper_gen._pick_target_nodes(
                    db, overview.weak_nodes, leaves, total
                )
            )
            db.commit()
            generated = self._paper_gen.generate_prepared_self_test(
                provider=provider,
                model=model,
                params=params,
                target_nodes=target_nodes,
                student_user_id=job.student_user_id,
                subject_code=job.subject_code,
                question_count=total,
                on_progress=on_progress,
            )
            if not generated:
                raise ValueError("Failed to generate self-test questions")
            paper = db.get(SelfTestPaper, job.paper_id)
            if paper is None:
                raise ValueError("self-test paper not found")
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
            db.flush()
            return len(generated)

        raise ValueError(f"unsupported paper gen purpose: {job.purpose}")

    @staticmethod
    def _make_progress_callback(job_id: uuid.UUID) -> ProgressCallback:
        from app.database import SessionLocal

        def on_progress(done: int, total_batches: int, message: str) -> None:
            progress_db = SessionLocal()
            try:
                progress_db.execute(
                    update(PaperGenJob)
                    .where(PaperGenJob.id == job_id)
                    .values(
                        progress_json={
                            "done": done,
                            "total": total_batches,
                            "message": message,
                        }
                    )
                )
                progress_db.commit()
            finally:
                progress_db.close()

        return on_progress

    def _run_one_isolated(self, job_id: uuid.UUID, now: datetime) -> None:
        from app.database import SessionLocal

        claim_db = SessionLocal()
        try:
            job = claim_db.get(PaperGenJob, job_id)
            if job is None:
                return
            claimed = claim_db.execute(
                update(PaperGenJob)
                .where(
                    PaperGenJob.id == job_id,
                    PaperGenJob.status.in_(("pending", "retry")),
                )
                .values(status="running", locked_at=now)
            )
            if claimed.rowcount == 0:
                claim_db.rollback()
                return
            claim_db.commit()
            attempts = job.attempts
            purpose = job.purpose
            paper_id = job.paper_id
        finally:
            claim_db.close()

        try:
            generated_count = self._execute_job_isolated(job_id)
            finish_db = SessionLocal()
            try:
                finish_db.execute(
                    update(PaperGenJob)
                    .where(PaperGenJob.id == job_id)
                    .values(
                        status="succeeded",
                        locked_at=None,
                        attempts=attempts + 1,
                        last_error=None,
                        progress_json={
                            "done": generated_count,
                            "total": generated_count,
                            "message": "题目生成完成",
                        },
                        result_json={"paper_id": str(paper_id)},
                    )
                )
                finish_db.commit()
            finally:
                finish_db.close()
        except Exception as exc:  # noqa: BLE001
            next_attempt = attempts + 1
            failed = next_attempt >= 3
            fail_db = SessionLocal()
            try:
                fail_db.execute(
                    update(PaperGenJob)
                    .where(PaperGenJob.id == job_id)
                    .values(
                        status="failed" if failed else "retry",
                        locked_at=None,
                        attempts=next_attempt,
                        last_error=str(exc),
                        run_after=now + timedelta(seconds=15),
                    )
                )
                self._mark_paper_failed(fail_db, purpose, paper_id)
                fail_db.commit()
            finally:
                fail_db.close()

    def _execute_job_isolated(self, job_id: uuid.UUID) -> int:
        from app.database import SessionLocal

        prep_db = SessionLocal()
        try:
            job = prep_db.get(PaperGenJob, job_id)
            if job is None:
                raise ValueError("job not found")
            student = prep_db.get(User, job.student_user_id)
            if student is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "student not found")

            policy = self._paper_gen._policy(prep_db, student.org_id)
            provider = policy.provider if policy is not None else None
            model = policy.model if policy is not None else None
            params = dict(policy.params or {}) if policy is not None else {}
            on_progress = self._make_progress_callback(job_id)

            if job.purpose == "placement":
                paper = prep_db.get(PlacementPaper, job.paper_id)
                if paper is None:
                    raise ValueError("placement paper not found")
                overview = ReportService.overview(
                    prep_db,
                    ReportQuery(
                        student_user_id=job.student_user_id,
                        subject_code=job.subject_code,
                    ),
                )
                placement_context = build_placement_context(
                    prep_db,
                    student_user_id=job.student_user_id,
                    subject_code=job.subject_code,
                )
                leaves = leaf_nodes_for_placement(
                    prep_db,
                    subject_code=job.subject_code,
                    exam_year=placement_context.exam_year,
                )
                if not leaves:
                    raise ValueError("syllabus missing for subject")
                placement_slots = materialize_placement_slots(
                    build_placement_slots(
                        prep_db, placement_context, leaves, overview.weak_nodes
                    )
                )
                prep_db.execute(
                    delete(PlacementQuestion).where(PlacementQuestion.paper_id == paper.id)
                )
                prep_db.commit()
                paper_id = paper.id
                student_user_id = job.student_user_id
                subject_code = job.subject_code
            elif job.purpose == "self_test":
                paper = prep_db.get(SelfTestPaper, job.paper_id)
                if paper is None:
                    raise ValueError("self-test paper not found")
                total = DEFAULT_QUESTION_COUNT
                overview = ReportService.overview(
                    prep_db,
                    ReportQuery(
                        student_user_id=job.student_user_id,
                        subject_code=job.subject_code,
                    ),
                )
                leaves = self._paper_gen._leaf_nodes(prep_db, job.subject_code)
                if not leaves:
                    raise ValueError("syllabus missing for subject")
                target_nodes = materialize_syllabus_nodes(
                    self._paper_gen._pick_target_nodes(
                        prep_db, overview.weak_nodes, leaves, total
                    )
                )
                prep_db.commit()
                paper_id = paper.id
                student_user_id = job.student_user_id
                subject_code = job.subject_code
                question_count = total
            else:
                raise ValueError(f"unsupported paper gen purpose: {job.purpose}")
        finally:
            prep_db.close()

        if job.purpose == "placement":
            generated = self._paper_gen.generate_prepared_placement(
                provider=provider,
                model=model,
                params=params,
                placement_context=placement_context,
                placement_slots=placement_slots,
                student_user_id=student_user_id,
                subject_code=subject_code,
                on_progress=on_progress,
            )
        else:
            generated = self._paper_gen.generate_prepared_self_test(
                provider=provider,
                model=model,
                params=params,
                target_nodes=target_nodes,
                student_user_id=student_user_id,
                subject_code=subject_code,
                question_count=question_count,
                on_progress=on_progress,
            )

        if not generated:
            raise ValueError("Failed to generate questions")

        save_db = SessionLocal()
        try:
            if job.purpose == "placement":
                paper = save_db.get(PlacementPaper, paper_id)
                if paper is None:
                    raise ValueError("placement paper not found")
                for q in generated:
                    save_db.add(
                        PlacementQuestion(
                            paper_id=paper.id,
                            seq=q.seq,
                            knowledge_node_id=q.knowledge_node_id,
                            q_type=q.q_type,
                            stem=q.stem,
                            choices_json=q.choices_json,
                            answer_key=q.answer_key,
                            points=q.points,
                            rubric_json=q.rubric_json,
                        )
                    )
                paper.status = "ready"
            else:
                paper = save_db.get(SelfTestPaper, paper_id)
                if paper is None:
                    raise ValueError("self-test paper not found")
                for q in generated:
                    save_db.add(
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
            save_db.commit()
            return len(generated)
        finally:
            save_db.close()

    @staticmethod
    def _mark_paper_failed(db: Session, purpose: str, paper_id: uuid.UUID) -> None:
        if purpose == "placement":
            paper = db.get(PlacementPaper, paper_id)
            if paper is not None:
                paper.status = "failed"
        elif purpose == "self_test":
            paper = db.get(SelfTestPaper, paper_id)
            if paper is not None:
                paper.status = "failed"


def kick_paper_gen_job(job_id: uuid.UUID) -> None:
    with _kick_lock:
        existing = _kick_threads.get(job_id)
        if existing is not None and existing.is_alive():
            return

        def _work() -> None:
            try:
                PaperGenJobRunner()._run_one_isolated(
                    job_id, datetime.now(timezone.utc)
                )
            finally:
                with _kick_lock:
                    _kick_threads.pop(job_id, None)

        thread = threading.Thread(
            target=_work,
            daemon=True,
            name=f"paper-gen-{job_id}",
        )
        _kick_threads[job_id] = thread
        thread.start()


def run_paper_gen_job_if_needed(db: Session, job_id: uuid.UUID | None) -> None:
    if job_id is not None:
        PaperGenJobRunner().run_pending(db, limit=1, job_id=job_id)
