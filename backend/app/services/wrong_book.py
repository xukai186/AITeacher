from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    PlacementAnswer,
    PlacementPaper,
    PlacementQuestion,
    PlacementSubmission,
    SelfTestAnswer,
    SelfTestPaper,
    SelfTestQuestion,
    SelfTestSubmission,
    WrongBookItem,
)
from app.services.learning_events import LearningEventService


class WrongBookService:
    @staticmethod
    def _add_wrong_item(
        db: Session,
        *,
        student_user_id: uuid.UUID,
        subject_code: str,
        knowledge_node_id: uuid.UUID | None,
        source_type: str,
        source_id: uuid.UUID,
        question_snapshot: dict,
        answer_snapshot: dict,
        correct_snapshot: dict,
    ) -> WrongBookItem:
        item = WrongBookItem(
            student_user_id=student_user_id,
            subject_code=subject_code,
            knowledge_node_id=knowledge_node_id,
            source_type=source_type,
            source_id=source_id,
            question_snapshot_json=question_snapshot,
            answer_snapshot_json=answer_snapshot,
            correct_snapshot_json=correct_snapshot,
            status="active",
            wrong_count=1,
        )
        db.add(item)
        db.flush()
        LearningEventService.record(
            db,
            student_user_id=student_user_id,
            event_type="wrong_added",
            subject_code=subject_code,
            ref_type="wrong_book_item",
            ref_id=item.id,
            payload={"source_type": source_type, "source_id": str(source_id)},
        )
        return item

    @staticmethod
    def ingest_from_placement_submission(db: Session, submission_id: uuid.UUID) -> int:
        submission = db.get(PlacementSubmission, submission_id)
        if submission is None:
            return 0
        paper = db.get(PlacementPaper, submission.paper_id)
        if paper is None:
            return 0

        answers = (
            db.execute(select(PlacementAnswer).where(PlacementAnswer.submission_id == submission_id))
            .scalars()
            .all()
        )
        if not answers:
            return 0

        questions = {
            q.id: q
            for q in db.execute(select(PlacementQuestion).where(PlacementQuestion.paper_id == submission.paper_id))
            .scalars()
            .all()
        }

        created = 0
        for ans in answers:
            q = questions.get(ans.question_id)
            if q is None:
                continue
            if ans.is_correct:
                continue

            WrongBookService._add_wrong_item(
                db,
                student_user_id=submission.student_user_id,
                subject_code=paper.subject_code,
                knowledge_node_id=q.knowledge_node_id,
                source_type="placement",
                source_id=submission.id,
                question_snapshot={
                    "id": str(q.id),
                    "seq": q.seq,
                    "q_type": q.q_type,
                    "stem": q.stem,
                    "choices": q.choices_json,
                    "points": q.points,
                },
                answer_snapshot={"content": ans.content},
                correct_snapshot={"answer_key": q.answer_key},
            )
            created += 1

        db.flush()
        return created

    @staticmethod
    def ingest_from_self_test_submission(db: Session, submission_id: uuid.UUID) -> int:
        submission = db.get(SelfTestSubmission, submission_id)
        if submission is None:
            return 0
        paper = db.get(SelfTestPaper, submission.paper_id)
        if paper is None:
            return 0

        answers = (
            db.execute(select(SelfTestAnswer).where(SelfTestAnswer.submission_id == submission_id))
            .scalars()
            .all()
        )
        if not answers:
            return 0

        questions = {
            q.id: q
            for q in db.execute(
                select(SelfTestQuestion).where(SelfTestQuestion.paper_id == submission.paper_id)
            )
            .scalars()
            .all()
        }

        created = 0
        for ans in answers:
            q = questions.get(ans.question_id)
            if q is None:
                continue
            key = (q.answer_key or "").strip()

            is_wrong = True
            if q.q_type in ("single_choice", "multi_choice", "fill_blank"):
                is_wrong = ans.content.strip() != key

            if not is_wrong:
                continue

            WrongBookService._add_wrong_item(
                db,
                student_user_id=submission.student_user_id,
                subject_code=paper.subject_code,
                knowledge_node_id=q.knowledge_node_id,
                source_type="self_test",
                source_id=submission.id,
                question_snapshot={
                    "id": str(q.id),
                    "seq": q.seq,
                    "q_type": q.q_type,
                    "stem": q.stem,
                    "choices": q.choices_json,
                    "points": q.points,
                },
                answer_snapshot={"content": ans.content},
                correct_snapshot={"answer_key": q.answer_key},
            )
            created += 1

        db.flush()
        return created

    @staticmethod
    def get_item(
        db: Session, student_user_id: uuid.UUID, item_id: uuid.UUID
    ) -> WrongBookItem:
        item = db.get(WrongBookItem, item_id)
        if item is None or item.student_user_id != student_user_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "wrong book item not found")
        return item

    @staticmethod
    def list_items(
        db: Session,
        student_user_id: uuid.UUID,
        subject_code: str | None = None,
        source_type: str | None = None,
        knowledge_node_id: uuid.UUID | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[WrongBookItem]:
        stmt = select(WrongBookItem).where(WrongBookItem.student_user_id == student_user_id)
        if subject_code:
            stmt = stmt.where(WrongBookItem.subject_code == subject_code)
        if source_type:
            stmt = stmt.where(WrongBookItem.source_type == source_type)
        if knowledge_node_id:
            stmt = stmt.where(WrongBookItem.knowledge_node_id == knowledge_node_id)
        if status:
            stmt = stmt.where(WrongBookItem.status == status)
        else:
            stmt = stmt.where(WrongBookItem.status.in_(("active", "mastered")))
        stmt = stmt.order_by(WrongBookItem.created_at.desc())
        stmt = stmt.limit(limit).offset(offset)
        return db.execute(stmt).scalars().all()
