from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ChatMessage, ChatSession, ModelPolicy, User
from app.models.chat import AgentType
from app.services.model_gateway import ModelGateway, ModelGatewayRequest


class ChatService:
    def __init__(self, model_gateway: ModelGateway | None = None) -> None:
        self._model_gateway = model_gateway or ModelGateway()

    def post_message(
        self,
        db: Session,
        student_user: User,
        agent_type: str,
        subject_code: str | None,
        message: str,
    ) -> tuple[str, str]:
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

        db.add(ChatMessage(session_id=session.id, role="user", content=message))

        policy = db.execute(
            select(ModelPolicy).where(ModelPolicy.org_id == student_user.org_id, ModelPolicy.scene == "chat")
        ).scalar_one_or_none()
        provider = policy.provider if policy is not None else "mock"
        model = policy.model if policy is not None else "mock-v1"
        params = policy.params if policy is not None else {}

        prompt = "\n".join(
            [
                "You are a helpful tutor.",
                f"Agent type: {agent_type}",
                f"Subject: {subject_code or 'none'}",
                f"User: {message}",
            ]
        )
        assistant_message = self._model_gateway.generate(
            ModelGatewayRequest(provider=provider, model=model, scene="chat", prompt=prompt, params=params)
        ).text

        db.add(ChatMessage(session_id=session.id, role="assistant", content=assistant_message))
        db.commit()
        return str(session.id), assistant_message

