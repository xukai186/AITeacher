from __future__ import annotations

import hashlib
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import MasterySnapshot, PlacementAnswer, PlacementPaper, PlacementResult, PlacementSubmission, StudentSubject, SyllabusNode
from app.models.placement import PlacementQuestion
from app.schemas.placement import (
    PlacementPaperDetail,
    PlacementPaperSummary,
    PlacementQuestionOut,
    PlacementSubmitIn,
    PlacementSubmitOut,
    PlacementStartOut,
    PlacementSubjectStatus,
)
from app.services.mastery import MasteryService
from app.seed_syllabus import seed_minimal_syllabus

QUESTIONS_PER_SUBJECT = 10
CHOICE_KEYS = ("A", "B", "C", "D")
Q_TYPE = "single_choice"


class PlacementService:
    @staticmethod
    def _ensure_syllabus(db: Session) -> None:
        count = db.execute(select(SyllabusNode.id).limit(1)).scalar_one_or_none()
        if count is None:
            seed_minimal_syllabus(db)
            db.flush()
        count = db.execute(select(SyllabusNode.id).limit(1)).scalar_one_or_none()
        if count is None:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Syllabus not seeded; ask an admin to run syllabus seed",
            )

    @staticmethod
    def _leaf_nodes(db: Session, subject_code: str) -> list[SyllabusNode]:
        nodes = list(
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
    def _generate_questions(
        cls,
        db: Session,
        paper: PlacementPaper,
        student_user_id: uuid.UUID,
        subject_code: str,
    ) -> None:
        leaves = cls._leaf_nodes(db, subject_code)
        if not leaves:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                f"No syllabus nodes for subject {subject_code}; ask an admin to seed syllabus",
            )

        for seq in range(1, QUESTIONS_PER_SUBJECT + 1):
            node = leaves[(seq - 1) % len(leaves)]
            key = cls._answer_key(student_user_id, subject_code, seq)
            choices = [
                {"key": letter, "text": f"{node.name} — 选项{letter}"}
                for letter in CHOICE_KEYS
            ]
            db.add(
                PlacementQuestion(
                    paper_id=paper.id,
                    seq=seq,
                    knowledge_node_id=node.id,
                    q_type=Q_TYPE,
                    stem=f"【{node.name}】请选择最符合考纲要求的选项（第{seq}题）",
                    choices_json=choices,
                    answer_key=key,
                    points=1,
                )
            )

    @classmethod
    def _get_or_create_paper(
        cls, db: Session, student_user_id: uuid.UUID, subject_code: str
    ) -> PlacementPaper:
        paper = db.execute(
            select(PlacementPaper).where(
                PlacementPaper.student_user_id == student_user_id,
                PlacementPaper.subject_code == subject_code,
            )
        ).scalar_one_or_none()
        if paper is not None:
            return paper

        paper = PlacementPaper(
            student_user_id=student_user_id,
            subject_code=subject_code,
            status="ready",
        )
        db.add(paper)
        db.flush()
        cls._generate_questions(db, paper, student_user_id, subject_code)
        return paper

    @classmethod
    def start(cls, db: Session, student_user_id: uuid.UUID) -> PlacementStartOut:
        cls._ensure_syllabus(db)

        subject_codes = list(
            db.execute(
                select(StudentSubject.subject_code).where(
                    StudentSubject.student_user_id == student_user_id,
                    StudentSubject.enabled.is_(True),
                )
            )
            .scalars()
            .all()
        )
        if not subject_codes:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "no enabled subjects")

        subjects: list[PlacementSubjectStatus] = []
        for subject_code in subject_codes:
            paper = cls._get_or_create_paper(db, student_user_id, subject_code)
            subjects.append(
                PlacementSubjectStatus(
                    subject_code=subject_code,
                    status="ready",
                    paper_id=paper.id,
                )
            )
        db.commit()
        return PlacementStartOut(subjects=subjects)

    @classmethod
    def list_papers(cls, db: Session, student_user_id: uuid.UUID) -> list[PlacementPaperSummary]:
        papers = list(
            db.execute(
                select(PlacementPaper)
                .where(PlacementPaper.student_user_id == student_user_id)
                .order_by(PlacementPaper.created_at)
            )
            .scalars()
            .all()
        )
        return [
            PlacementPaperSummary(
                id=p.id,
                subject_code=p.subject_code,
                status=p.status,
                title=p.subject_code,
                created_at=p.created_at,
            )
            for p in papers
        ]

    @classmethod
    def get_paper(
        cls, db: Session, student_user_id: uuid.UUID, paper_id: uuid.UUID
    ) -> PlacementPaperDetail:
        paper = db.get(PlacementPaper, paper_id)
        if paper is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "paper not found")
        if paper.student_user_id != student_user_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "paper not found")

        questions = list(
            db.execute(
                select(PlacementQuestion)
                .where(PlacementQuestion.paper_id == paper_id)
                .order_by(PlacementQuestion.seq)
            )
            .scalars()
            .all()
        )
        return PlacementPaperDetail(
            id=paper.id,
            subject_code=paper.subject_code,
            status=paper.status,
            title=paper.subject_code,
            created_at=paper.created_at,
            questions=[cls._question_out(q) for q in questions],
        )

    @classmethod
    def submit(
        cls,
        db: Session,
        student_user_id: uuid.UUID,
        paper_id: uuid.UUID,
        payload: PlacementSubmitIn,
    ) -> PlacementSubmitOut:
        paper = db.get(PlacementPaper, paper_id)
        if paper is None or paper.student_user_id != student_user_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "paper not found")

        questions = {
            q.id: q
            for q in db.execute(
                select(PlacementQuestion).where(PlacementQuestion.paper_id == paper_id)
            )
            .scalars()
            .all()
        }
        if not questions:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "paper has no questions")

        submission = db.execute(
            select(PlacementSubmission).where(
                PlacementSubmission.paper_id == paper_id,
                PlacementSubmission.student_user_id == student_user_id,
            )
        ).scalar_one_or_none()
        if submission is None:
            submission = PlacementSubmission(
                paper_id=paper_id,
                student_user_id=student_user_id,
                status="submitted",
                submitted_at=func.now(),
            )
            db.add(submission)
            db.flush()

        total_score = 0
        correct_by_node: dict[uuid.UUID, tuple[int, int]] = {}
        for ans in payload.answers:
            q = questions.get(ans.question_id)
            if q is None:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid question_id")
            is_correct = ans.content.strip() == (q.answer_key or "")
            score = q.points if is_correct else 0
            total_score += score

            db.add(
                PlacementAnswer(
                    submission_id=submission.id,
                    question_id=q.id,
                    content=ans.content,
                    is_correct=is_correct,
                    score=score,
                )
            )

            if q.knowledge_node_id is not None:
                prev_correct, prev_total = correct_by_node.get(q.knowledge_node_id, (0, 0))
                correct_by_node[q.knowledge_node_id] = (
                    prev_correct + (1 if is_correct else 0),
                    prev_total + 1,
                )

        mastery_levels = MasteryService.placement_levels(correct_by_node)

        result = db.execute(
            select(PlacementResult).where(PlacementResult.paper_id == paper_id)
        ).scalar_one_or_none()
        if result is None:
            result = PlacementResult(
                paper_id=paper_id,
                total_score=total_score,
                mastery_json=mastery_levels,
            )
            db.add(result)
        else:
            result.total_score = total_score
            result.mastery_json = mastery_levels

        existing = db.execute(
            select(MasterySnapshot.id).where(
                MasterySnapshot.student_user_id == student_user_id,
                MasterySnapshot.subject_code == paper.subject_code,
                MasterySnapshot.version == 1,
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "placement already submitted")

        db.add(
            MasterySnapshot(
                student_user_id=student_user_id,
                subject_code=paper.subject_code,
                version=1,
                mastery_json=mastery_levels,
            )
        )

        db.commit()
        return PlacementSubmitOut(
            paper_id=paper_id,
            total_score=total_score,
            mastery_json=mastery_levels,
        )

    @staticmethod
    def _question_out(question: PlacementQuestion) -> PlacementQuestionOut:
        choices_raw = question.choices_json or []
        return PlacementQuestionOut(
            id=question.id,
            seq=question.seq,
            q_type=question.q_type,
            stem=question.stem,
            choices=choices_raw,
            answer_key=question.answer_key,
        )
