from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ModelPolicy, User, WrongBookItem
from app.services.chat_tool_loop import ChatToolLoop

EXPLAIN_USER_MESSAGE_TEMPLATE = (
    "请讲解错题本条目 item_id={item_id}。"
    "结合我的当时作答说明错因与正确思路。"
)


@dataclass
class WrongBookExplainResult:
    explanation_text: str
    from_cache: bool
    explanation_created_at: datetime | None


class WrongBookExplainService:
    def __init__(self, tool_loop: ChatToolLoop | None = None) -> None:
        self._tool_loop = tool_loop or ChatToolLoop()

    def explain(
        self,
        db: Session,
        *,
        item: WrongBookItem,
        student_user_id: uuid.UUID,
        regenerate: bool,
    ) -> WrongBookExplainResult:
        if item.explanation_text and not regenerate:
            return WrongBookExplainResult(
                explanation_text=item.explanation_text,
                from_cache=True,
                explanation_created_at=item.explanation_created_at,
            )

        student_user = db.get(User, student_user_id)
        org_id = student_user.org_id if student_user is not None else None
        policy = None
        if org_id is not None:
            policy = db.execute(
                select(ModelPolicy).where(
                    ModelPolicy.org_id == org_id,
                    ModelPolicy.scene == "chat",
                )
            ).scalar_one_or_none()
        provider = policy.provider if policy is not None else "mock"
        model = policy.model if policy is not None else "mock-v1"
        params = policy.params if policy is not None else {}

        turn = self._tool_loop.run(
            db,
            student_user_id=student_user_id,
            agent_type="subject",
            subject_code=item.subject_code,
            provider=provider,
            model=model,
            params=params,
            history_messages=[],
            user_message=EXPLAIN_USER_MESSAGE_TEMPLATE.format(item_id=item.id),
        )
        item.explanation_text = turn.assistant_message
        item.explanation_created_at = datetime.now(timezone.utc)
        db.flush()
        return WrongBookExplainResult(
            explanation_text=item.explanation_text,
            from_cache=False,
            explanation_created_at=item.explanation_created_at,
        )
