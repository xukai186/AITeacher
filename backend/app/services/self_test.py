from __future__ import annotations

import uuid

from datetime import date, timedelta
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    SelfTestAnswer,
    SelfTestGrade,
    SelfTestPaper,
    SelfTestQuestion,
    SelfTestSubmission,
    StudentSubject,
    SyllabusNode,
    User,
)
from app.schemas.self_test import SelfTestSubmitIn
from app.services.grading import GradingService
from app.services.mastery import MasteryService
from app.services.plan_review_jobs import PlanReviewJobService
from app.services.self_test_eligibility import SelfTestEligibilityService
from app.services.learning_events import LearningEventService
from app.services.wrong_book import WrongBookService
from app.services.wrong_book_followup import WrongBookFollowUpService
from app.services.paper_gen import DEFAULT_QUESTION_COUNT, PaperGenService
from app.seed_syllabus import seed_minimal_syllabus

QUESTIONS_PER_PAPER = DEFAULT_QUESTION_COUNT


class SelfTestService:
    @staticmethod
    def _ensure_syllabus(db: Session) -> None:
        any_node = db.execute(select(SyllabusNode.id).limit(1)).scalar_one_or_none()
        if any_node is None:
            seed_minimal_syllabus(db)
            db.flush()

    @staticmethod
    def _leaf_nodes(db: Session, subject_code: str) -> list[SyllabusNode]:
        nodes = (
            db.execute(
                select(SyllabusNode)
                .where(SyllabusNode.subject_code == subject_code)
                .order_by(SyllabusNode.name)
            )
            .scalars()
            .all()
        )
        if not nodes:
            return []
        parent_ids = {n.parent_id for n in nodes if n.parent_id is not None}
        return [n for n in nodes if n.id not in parent_ids]

    @classmethod
    def generate(
        cls,
        db: Session,
        student_user_id: uuid.UUID,
        subject_code: str,
        *,
        skip_eligibility: bool = False,
    ) -> SelfTestPaper:
        cls._ensure_syllabus(db)

        if not skip_eligibility:
            eligibility = SelfTestEligibilityService().check(
                db, student_user_id=student_user_id, subject_code=subject_code
            )
            if not eligibility.allowed:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail={"code": "self_test_not_eligible", "reasons": eligibility.reasons},
                )

        enabled = db.execute(
            select(StudentSubject.id).where(
                StudentSubject.student_user_id == student_user_id,
                StudentSubject.subject_code == subject_code,
                StudentSubject.enabled.is_(True),
            )
        ).scalar_one_or_none()
        if enabled is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "subject not enabled")

        student = db.get(User, student_user_id)
        if student is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "student not found")

        paper = SelfTestPaper(
            student_user_id=student_user_id,
            subject_code=subject_code,
            status="ready",
            source="ai",
        )
        db.add(paper)
        db.flush()

        try:
            generated = PaperGenService().generate_for_self_test(
                db,
                org_id=student.org_id,
                student_user_id=student_user_id,
                subject_code=subject_code,
                question_count=QUESTIONS_PER_PAPER,
            )
        except ValueError as exc:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                str(exc),
            ) from exc

        if not generated:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Failed to generate self-test questions",
            )

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

        db.commit()
        return paper

    @staticmethod
    def list_papers(db: Session, student_user_id: uuid.UUID) -> list[SelfTestPaper]:
        return (
            db.execute(
                select(SelfTestPaper)
                .where(SelfTestPaper.student_user_id == student_user_id)
                .order_by(SelfTestPaper.created_at.desc())
            )
            .scalars()
            .all()
        )

    @staticmethod
    def get_paper(db: Session, student_user_id: uuid.UUID, paper_id: uuid.UUID) -> SelfTestPaper:
        paper = db.get(SelfTestPaper, paper_id)
        if paper is None or paper.student_user_id != student_user_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "paper not found")
        return paper

    @staticmethod
    def get_grade(db: Session, student_user_id: uuid.UUID, submission_id: uuid.UUID) -> SelfTestGrade:
        submission = db.get(SelfTestSubmission, submission_id)
        if submission is None or submission.student_user_id != student_user_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "submission not found")
        grade = db.execute(
            select(SelfTestGrade).where(SelfTestGrade.submission_id == submission_id)
        ).scalar_one_or_none()
        if grade is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "grade not found")
        return grade

    @staticmethod
    def submit(
        db: Session,
        student_user_id: uuid.UUID,
        org_id: uuid.UUID,
        paper_id: uuid.UUID,
        payload: SelfTestSubmitIn,
    ) -> SelfTestGrade:
        paper = db.get(SelfTestPaper, paper_id)
        if paper is None or paper.student_user_id != student_user_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "paper not found")

        existing = db.execute(
            select(SelfTestSubmission.id).where(
                SelfTestSubmission.paper_id == paper_id,
                SelfTestSubmission.student_user_id == student_user_id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "already submitted")

        submission = SelfTestSubmission(
            paper_id=paper_id,
            student_user_id=student_user_id,
            status="submitted",
            submitted_at=func.now(),
        )
        db.add(submission)
        db.flush()

        questions = {
            q.id: q
            for q in db.execute(select(SelfTestQuestion).where(SelfTestQuestion.paper_id == paper_id))
            .scalars()
            .all()
        }
        if not questions:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "paper has no questions")

        total_score = 0
        per_q: list[dict] = []
        grader = GradingService()
        for a in payload.answers:
            q = questions.get(a.question_id)
            if q is None:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid question_id")

            if q.q_type in ("single_choice", "multi_choice", "fill_blank"):
                score, is_correct = GradingService.grade_objective(q, a.content)
                detail = {"mode": "objective", "is_correct": is_correct}
            else:
                score, detail = grader.grade_subjective(db, org_id, q, a.content)
                is_correct = False

            total_score += score
            per_q.append(
                {
                    "question_id": str(q.id),
                    "seq": q.seq,
                    "score": score,
                    "points": q.points,
                    "detail": detail,
                }
            )

            db.add(
                SelfTestAnswer(
                    submission_id=submission.id,
                    question_id=q.id,
                    content=a.content,
                )
            )

        grade = SelfTestGrade(
            submission_id=submission.id,
            total_score=total_score,
            detail_json={"questions": per_q},
        )
        db.add(grade)

        db.flush()
        WrongBookService.ingest_from_self_test_submission(db, submission.id)
        LearningEventService.record(
            db,
            student_user_id=student_user_id,
            event_type="paper_submitted",
            subject_code=paper.subject_code,
            ref_type="self_test_submission",
            ref_id=submission.id,
            payload={"paper_id": str(paper_id), "total_score": total_score},
        )
        MasteryService.update_from_self_test_submission(db, submission.id)
        WrongBookFollowUpService().schedule_after_self_test(
            db,
            student_user_id=student_user_id,
            subject_code=paper.subject_code,
            submission_id=submission.id,
        )
        PlanReviewJobService().enqueue(
            db,
            student_user_id=student_user_id,
            subject_code=paper.subject_code,
            target_date=date.today() + timedelta(days=1),
            trigger="self_test_graded",
        )
        db.commit()
        return grade

