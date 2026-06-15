from __future__ import annotations

import uuid
from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import (
    MasterySnapshot,
    PlacementAnswer,
    PlacementPaper,
    PlacementResult,
    PlacementSubmission,
    StudentSubject,
    SyllabusNode,
    User,
)
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
from app.services.plan_review_jobs import PlanReviewJobService
from app.services.planning import PlanningService
from app.services.tasks import TaskGenerator
from app.services.learning_events import LearningEventService
from app.services.wrong_book import WrongBookService
from app.services.paper_gen import DEFAULT_QUESTION_COUNT, PaperGenService
from app.seed_syllabus import seed_minimal_syllabus

QUESTIONS_PER_SUBJECT = DEFAULT_QUESTION_COUNT
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
    def _legacy_template_stem(stem: str) -> bool:
        return "请选择最符合考纲要求的选项" in stem and "摸底·" not in stem

    @classmethod
    def _needs_regeneration(cls, db: Session, paper_id: uuid.UUID) -> bool:
        questions = list(
            db.execute(
                select(PlacementQuestion).where(PlacementQuestion.paper_id == paper_id)
            )
            .scalars()
            .all()
        )
        if not questions:
            return True
        return all(cls._legacy_template_stem(q.stem) for q in questions)

    @classmethod
    def _regenerate_questions(
        cls,
        db: Session,
        paper: PlacementPaper,
        student_user_id: uuid.UUID,
        subject_code: str,
    ) -> None:
        db.execute(delete(PlacementQuestion).where(PlacementQuestion.paper_id == paper.id))
        db.flush()
        db.commit()
        generated = cls._generate_questions_data(db, paper, student_user_id, subject_code)
        for q in generated:
            db.add(
                PlacementQuestion(
                    paper_id=paper.id,
                    seq=q.seq,
                    knowledge_node_id=q.knowledge_node_id,
                    q_type=q.q_type or Q_TYPE,
                    stem=q.stem,
                    choices_json=q.choices_json,
                    answer_key=q.answer_key,
                    points=q.points,
                )
            )
        db.flush()

    @classmethod
    def _generate_questions_data(
        cls,
        db: Session,
        paper: PlacementPaper,
        student_user_id: uuid.UUID,
        subject_code: str,
    ):
        student = db.get(User, student_user_id)
        if student is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "student not found")

        try:
            generated = PaperGenService().generate_for_placement(
                db,
                org_id=student.org_id,
                student_user_id=student_user_id,
                subject_code=subject_code,
                question_count=QUESTIONS_PER_SUBJECT,
            )
        except ValueError as exc:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                str(exc),
            ) from exc

        if not generated:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Failed to generate placement questions",
            )
        return generated

    @classmethod
    def _generate_questions(
        cls,
        db: Session,
        paper: PlacementPaper,
        student_user_id: uuid.UUID,
        subject_code: str,
    ) -> None:
        for q in cls._generate_questions_data(db, paper, student_user_id, subject_code):
            db.add(
                PlacementQuestion(
                    paper_id=paper.id,
                    seq=q.seq,
                    knowledge_node_id=q.knowledge_node_id,
                    q_type=q.q_type or Q_TYPE,
                    stem=q.stem,
                    choices_json=q.choices_json,
                    answer_key=q.answer_key,
                    points=q.points,
                )
            )

    @classmethod
    def _is_submitted(
        cls, db: Session, paper_id: uuid.UUID, student_user_id: uuid.UUID
    ) -> bool:
        existing = db.execute(
            select(PlacementSubmission.id).where(
                PlacementSubmission.paper_id == paper_id,
                PlacementSubmission.student_user_id == student_user_id,
            )
        ).scalar_one_or_none()
        return existing is not None

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
            if (
                not cls._is_submitted(db, paper.id, student_user_id)
                and cls._needs_regeneration(db, paper.id)
            ):
                cls._regenerate_questions(db, paper, student_user_id, subject_code)
            return paper

        paper = PlacementPaper(
            student_user_id=student_user_id,
            subject_code=subject_code,
            status="ready",
        )
        db.add(paper)
        db.flush()
        cls._regenerate_questions(db, paper, student_user_id, subject_code)
        return paper

    @classmethod
    def _subject_statuses(
        cls, db: Session, student_user_id: uuid.UUID, subject_codes: list[str]
    ) -> list[PlacementSubjectStatus]:
        subjects: list[PlacementSubjectStatus] = []
        for code in subject_codes:
            paper = db.execute(
                select(PlacementPaper).where(
                    PlacementPaper.student_user_id == student_user_id,
                    PlacementPaper.subject_code == code,
                )
            ).scalar_one_or_none()
            if paper is None:
                subjects.append(
                    PlacementSubjectStatus(subject_code=code, status="pending", paper_id=None)
                )
                continue
            submitted = cls._is_submitted(db, paper.id, student_user_id)
            subjects.append(
                PlacementSubjectStatus(
                    subject_code=code,
                    status="submitted" if submitted else "ready",
                    paper_id=paper.id,
                )
            )
        return subjects

    @classmethod
    def start(
        cls,
        db: Session,
        student_user_id: uuid.UUID,
        *,
        subject_code: str | None = None,
    ) -> PlacementStartOut:
        cls._ensure_syllabus(db)

        enabled_codes = list(
            db.execute(
                select(StudentSubject.subject_code).where(
                    StudentSubject.student_user_id == student_user_id,
                    StudentSubject.enabled.is_(True),
                )
            )
            .scalars()
            .all()
        )
        if not enabled_codes:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "no enabled subjects")

        target_code = subject_code
        if target_code is None:
            for code in enabled_codes:
                paper = db.execute(
                    select(PlacementPaper).where(
                        PlacementPaper.student_user_id == student_user_id,
                        PlacementPaper.subject_code == code,
                    )
                ).scalar_one_or_none()
                if paper is None or not cls._is_submitted(db, paper.id, student_user_id):
                    target_code = code
                    break
            if target_code is None:
                target_code = enabled_codes[0]
        elif target_code not in enabled_codes:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "subject not enabled")

        paper = cls._get_or_create_paper(db, student_user_id, target_code)
        submitted = cls._is_submitted(db, paper.id, student_user_id)
        db.commit()

        subjects = cls._subject_statuses(db, student_user_id, enabled_codes)
        primary = PlacementSubjectStatus(
            subject_code=target_code,
            status="submitted" if submitted else "ready",
            paper_id=paper.id,
        )
        others = [s for s in subjects if s.subject_code != target_code]
        others.sort(key=lambda item: (0 if item.status == "ready" else 1, item.subject_code))
        return PlacementStartOut(subjects=[primary, *others])

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

        if cls._is_submitted(db, paper_id, student_user_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "placement already submitted")

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
            select(MasterySnapshot).where(
                MasterySnapshot.student_user_id == student_user_id,
                MasterySnapshot.subject_code == paper.subject_code,
                MasterySnapshot.version == 1,
            )
        ).scalar_one_or_none()
        if existing is None:
            db.add(
                MasterySnapshot(
                    student_user_id=student_user_id,
                    subject_code=paper.subject_code,
                    version=1,
                    mastery_json=mastery_levels,
                )
            )
        else:
            existing.mastery_json = mastery_levels

        PlanningService().create_initial_plans(db, student_user_id=student_user_id)
        TaskGenerator().generate_next_7_days(db, student_user_id=student_user_id, today=date.today())

        db.flush()
        WrongBookService.ingest_from_placement_submission(db, submission.id)
        LearningEventService.record(
            db,
            student_user_id=student_user_id,
            event_type="paper_submitted",
            subject_code=paper.subject_code,
            ref_type="placement_submission",
            ref_id=submission.id,
            payload={"paper_id": str(paper_id), "total_score": total_score},
        )
        PlanReviewJobService().enqueue(
            db,
            student_user_id=student_user_id,
            subject_code=paper.subject_code,
            target_date=date.today() + timedelta(days=1),
            trigger="placement_completed",
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
