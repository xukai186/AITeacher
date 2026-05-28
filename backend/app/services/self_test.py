from __future__ import annotations

import hashlib
import uuid

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
)
from app.schemas.self_test import SelfTestSubmitIn
from app.services.grading import GradingService
from app.seed_syllabus import seed_minimal_syllabus

QUESTIONS_PER_PAPER = 10
CHOICE_KEYS = ("A", "B", "C", "D")


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

    @staticmethod
    def _answer_key(student_user_id: uuid.UUID, subject_code: str, seq: int) -> str:
        digest = hashlib.sha256(f"{student_user_id}:{subject_code}:{seq}".encode()).hexdigest()
        return CHOICE_KEYS[int(digest[:8], 16) % len(CHOICE_KEYS)]

    @classmethod
    def generate(cls, db: Session, student_user_id: uuid.UUID, subject_code: str) -> SelfTestPaper:
        cls._ensure_syllabus(db)

        enabled = db.execute(
            select(StudentSubject.id).where(
                StudentSubject.student_user_id == student_user_id,
                StudentSubject.subject_code == subject_code,
                StudentSubject.enabled.is_(True),
            )
        ).scalar_one_or_none()
        if enabled is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "subject not enabled")

        paper = SelfTestPaper(student_user_id=student_user_id, subject_code=subject_code, status="ready")
        db.add(paper)
        db.flush()

        leaves = cls._leaf_nodes(db, subject_code)
        if not leaves:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Syllabus not seeded for this subject",
            )

        for seq in range(1, QUESTIONS_PER_PAPER + 1):
            node = leaves[(seq - 1) % len(leaves)]
            key = cls._answer_key(student_user_id, subject_code, seq)
            choices = [{"key": k, "text": f"{node.name} — 选项{k}"} for k in CHOICE_KEYS]
            db.add(
                SelfTestQuestion(
                    paper_id=paper.id,
                    seq=seq,
                    knowledge_node_id=node.id,
                    q_type="single_choice",
                    stem=f"【{node.name}】请选择最符合要求的选项（第{seq}题）",
                    choices_json=choices,
                    answer_key=key,
                    points=1,
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
    def submit(
        db: Session,
        student_user_id: uuid.UUID,
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
                score, detail = grader.grade_subjective(q, a.content)
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
        db.commit()
        return grade

