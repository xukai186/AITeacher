from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import WrongBookItem
from app.services.learning_events import LearningEventService

MASTERY_GAP_DAYS = 1


@dataclass
class PracticeResult:
    is_correct: bool
    status: str
    consecutive_correct_count: int
    mastered: bool


class WrongBookMasteryService:
    @staticmethod
    def _is_correct(item: WrongBookItem, content: str) -> bool:
        q_type = (item.question_snapshot_json or {}).get("q_type", "")
        key = str((item.correct_snapshot_json or {}).get("answer_key") or "").strip()
        if q_type in ("single_choice", "multi_choice", "fill_blank") and key:
            return content.strip() == key
        return False

    def practice(
        self,
        db: Session,
        *,
        item: WrongBookItem,
        content: str,
        now: datetime | None = None,
    ) -> PracticeResult:
        if item.status == "archived":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "item is archived")

        ts = now or datetime.now(timezone.utc)
        item.last_practice_at = ts
        is_correct = self._is_correct(item, content)

        if is_correct:
            LearningEventService.record(
                db,
                student_user_id=item.student_user_id,
                event_type="wrong_practice_correct",
                subject_code=item.subject_code,
                ref_type="wrong_book_item",
                ref_id=item.id,
                payload={"content": content},
            )
            if item.status == "active":
                if item.consecutive_correct_count == 0:
                    item.consecutive_correct_count = 1
                    item.first_correct_at = ts
                elif item.consecutive_correct_count == 1 and item.first_correct_at:
                    gap = ts - item.first_correct_at
                    if gap >= timedelta(days=MASTERY_GAP_DAYS):
                        item.consecutive_correct_count = 2
                        item.status = "mastered"
                        item.mastered_at = ts
                        LearningEventService.record(
                            db,
                            student_user_id=item.student_user_id,
                            event_type="wrong_mastered",
                            subject_code=item.subject_code,
                            ref_type="wrong_book_item",
                            ref_id=item.id,
                        )
        else:
            item.consecutive_correct_count = 0
            item.first_correct_at = None
            LearningEventService.record(
                db,
                student_user_id=item.student_user_id,
                event_type="wrong_practice_wrong",
                subject_code=item.subject_code,
                ref_type="wrong_book_item",
                ref_id=item.id,
                payload={"content": content},
            )

        db.flush()
        return PracticeResult(
            is_correct=is_correct,
            status=item.status,
            consecutive_correct_count=item.consecutive_correct_count,
            mastered=item.status == "mastered",
        )

    @staticmethod
    def archive(db: Session, *, item: WrongBookItem) -> WrongBookItem:
        if item.status != "mastered":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "only mastered items can be archived",
            )
        item.status = "archived"
        LearningEventService.record(
            db,
            student_user_id=item.student_user_id,
            event_type="wrong_archived",
            subject_code=item.subject_code,
            ref_type="wrong_book_item",
            ref_id=item.id,
        )
        db.flush()
        return item
