from __future__ import annotations

import hashlib
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PlacementPaper, StudentSubject, SyllabusNode
from app.models.placement import PlacementQuestion
from app.schemas.placement import (
    PlacementPaperDetail,
    PlacementPaperSummary,
    PlacementQuestionOut,
    PlacementStartOut,
    PlacementSubjectStatus,
)
from app.seed_syllabus import seed_minimal_syllabus

QUESTIONS_PER_SUBJECT = 10
CHOICE_KEYS = ("A", "B", "C", "D")
Q_TYPE = "single_choice"


class PlacementService:
    @staticmethod
    def _paper_title(student_user_id: uuid.UUID, subject_code: str) -> str:
        return f"placement:{student_user_id}:{subject_code}"

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
                .order_by(SyllabusNode.code)
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
                {"key": letter, "text": f"{node.title} — 选项{letter}"}
                for letter in CHOICE_KEYS
            ]
            db.add(
                PlacementQuestion(
                    paper_id=paper.id,
                    seq=seq,
                    prompt=f"【{node.title}】请选择最符合考纲要求的选项（第{seq}题）",
                    choices_json=choices,
                    answer_json={"key": key, "q_type": Q_TYPE, "knowledge_node_id": str(node.id)},
                )
            )

    @classmethod
    def _get_or_create_paper(
        cls, db: Session, student_user_id: uuid.UUID, subject_code: str
    ) -> PlacementPaper:
        title = cls._paper_title(student_user_id, subject_code)
        paper = db.execute(
            select(PlacementPaper).where(PlacementPaper.title == title)
        ).scalar_one_or_none()
        if paper is not None:
            return paper

        paper = PlacementPaper(
            subject_code=subject_code,
            title=title,
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
        prefix = f"placement:{student_user_id}:"
        papers = list(
            db.execute(
                select(PlacementPaper)
                .where(PlacementPaper.title.like(f"{prefix}%"))
                .order_by(PlacementPaper.created_at)
            )
            .scalars()
            .all()
        )
        return [
            PlacementPaperSummary(
                id=p.id,
                subject_code=p.subject_code,
                status="ready",
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
        expected_title = cls._paper_title(student_user_id, paper.subject_code)
        if paper.title != expected_title:
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
            status="ready",
            title=paper.subject_code,
            created_at=paper.created_at,
            questions=[cls._question_out(q) for q in questions],
        )

    @staticmethod
    def _question_out(question: PlacementQuestion) -> PlacementQuestionOut:
        answer = question.answer_json or {}
        choices_raw = question.choices_json or []
        return PlacementQuestionOut(
            id=question.id,
            seq=question.seq,
            q_type=str(answer.get("q_type", Q_TYPE)),
            stem=question.prompt,
            choices=choices_raw,
            answer_key=str(answer.get("key", "")),
        )
