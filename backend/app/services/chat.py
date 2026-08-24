from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.models import ChatMessage, ChatSession, ModelPolicy, User
from app.models.chat import AgentType
from app.services.chat_tool_loop import TOOL_CALLS_PREFIX, ChatToolLoop
from app.services.model_gateway import ModelGateway


class ChatService:
    def __init__(
        self,
        model_gateway: ModelGateway | None = None,
        tool_loop: ChatToolLoop | None = None,
    ) -> None:
        self._model_gateway = model_gateway or ModelGateway()
        self._tool_loop = tool_loop or ChatToolLoop(model_gateway=self._model_gateway)

    def post_message(
        self,
        db: Session,
        student_user: User,
        agent_type: str,
        subject_code: str | None,
        message: str,
    ) -> tuple[str, str, list[str]]:
        session = db.execute(
            select(ChatSession).where(
                ChatSession.student_user_id == student_user.id,
                ChatSession.agent_type == AgentType(agent_type),
                ChatSession.subject_code == subject_code,
            )
        ).scalar_one_or_none()

        if session is None:
            session = ChatSession(
                student_user_id=student_user.id,
                agent_type=AgentType(agent_type),
                subject_code=subject_code,
            )
            db.add(session)
            db.flush()

        db.add(self._new_message(session.id, "user", message))
        db.flush()

        prior_rows = (
            db.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == session.id)
                .order_by(*self._message_order())
            )
            .scalars()
            .all()
        )
        prior_rows = prior_rows[:-1]
        history_messages = ChatToolLoop.history_from_db_rows(prior_rows)

        policy = db.execute(
            select(ModelPolicy).where(
                ModelPolicy.org_id == student_user.org_id, ModelPolicy.scene == "chat"
            )
        ).scalar_one_or_none()
        provider = policy.provider if policy is not None else "mock"
        model = policy.model if policy is not None else "mock-v1"
        params = policy.params if policy is not None else {}

        turn = self._tool_loop.run(
            db,
            student_user_id=student_user.id,
            agent_type=agent_type,
            subject_code=subject_code,
            provider=provider,
            model=model,
            params=params,
            history_messages=history_messages,
            user_message=message,
        )

        for msg in turn.api_messages:
            role = msg.get("role")
            content = msg.get("content")
            if role == "assistant" and content and str(content).startswith(TOOL_CALLS_PREFIX):
                db.add(self._new_message(session.id, "assistant", str(content)))
            elif role == "tool":
                db.add(
                    self._new_message(
                        session.id,
                        "tool",
                        json.dumps(
                            {
                                "tool_call_id": msg.get("tool_call_id"),
                                "name": msg.get("name"),
                                "result": json.loads(str(msg.get("content") or "{}")),
                            },
                            ensure_ascii=False,
                        ),
                    )
                )

        db.add(self._new_message(session.id, "assistant", turn.assistant_message))
        db.commit()
        return str(session.id), turn.assistant_message, turn.tools_used

    def list_history(
        self,
        db: Session,
        *,
        student_user: User,
        agent_type: str,
        subject_code: str | None,
    ) -> tuple[str | None, list[dict[str, str]]]:
        session = db.execute(
            select(ChatSession).where(
                ChatSession.student_user_id == student_user.id,
                ChatSession.agent_type == AgentType(agent_type),
                ChatSession.subject_code == subject_code,
            )
        ).scalar_one_or_none()
        if session is None:
            return None, []

        rows = (
            db.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == session.id)
                .order_by(*self._message_order())
            )
            .scalars()
            .all()
        )
        messages: list[dict[str, str]] = []
        for row in rows:
            if row.role == "user":
                messages.append({"role": "user", "content": row.content})
            elif (
                row.role == "assistant"
                and not row.content.startswith(TOOL_CALLS_PREFIX)
            ):
                messages.append({"role": "assistant", "content": row.content})
        return str(session.id), messages

    @staticmethod
    def _new_message(session_id, role: str, content: str) -> ChatMessage:
        return ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            created_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _message_order():
        return (
            ChatMessage.created_at,
            case(
                (ChatMessage.role == "user", 0),
                (ChatMessage.content.startswith(TOOL_CALLS_PREFIX), 1),
                (ChatMessage.role == "tool", 2),
                else_=3,
            ),
            ChatMessage.id,
        )
