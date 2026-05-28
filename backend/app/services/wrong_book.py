from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SelfTestAnswer, SelfTestPaper, SelfTestQuestion, SelfTestSubmission, WrongBookItem


class WrongBookService:
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

            # MVP: treat as wrong if objective and mismatch, or subjective has no answer_key.
            is_wrong = True
            if q.q_type in ("single_choice", "multi_choice", "fill_blank"):
                is_wrong = ans.content.strip() != key

            if not is_wrong:
                continue

            db.add(
                WrongBookItem(
                    student_user_id=submission.student_user_id,
                    subject_code=paper.subject_code,
                    knowledge_node_id=q.knowledge_node_id,
                    source_type="self_test",
                    source_id=submission.id,
                    question_snapshot_json={
                        "id": str(q.id),
                        "seq": q.seq,
                        "q_type": q.q_type,
                        "stem": q.stem,
                        "choices": q.choices_json,
                        "points": q.points,
                    },
                    answer_snapshot_json={"content": ans.content},
                    correct_snapshot_json={"answer_key": q.answer_key},
                )
            )
            created += 1

        db.flush()
        return created

    @staticmethod
    def list_items(
        db: Session, student_user_id: uuid.UUID, subject_code: str | None = None
    ) -> list[WrongBookItem]:
        stmt = select(WrongBookItem).where(WrongBookItem.student_user_id == student_user_id)
        if subject_code:
            stmt = stmt.where(WrongBookItem.subject_code == subject_code)
        stmt = stmt.order_by(WrongBookItem.created_at.desc())
        return db.execute(stmt).scalars().all()

