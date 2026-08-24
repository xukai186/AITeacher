from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.permissions import require_roles
from app.database import get_db
from app.models import User, UserRole
from app.schemas.chat import ChatHistoryOut, ChatHistoryMessageOut, ChatPostRequest, ChatPostResponse
from app.services.chat import ChatService

router = APIRouter(tags=["chat"])
require_student = require_roles(UserRole.student)


@router.get("/chat", response_model=ChatHistoryOut)
def get_chat_history(
    agent_type: str = Query(pattern="^(planner|subject)$"),
    subject_code: str | None = None,
    db: Session = Depends(get_db),
    student_user: User = Depends(require_student),
) -> ChatHistoryOut:
    session_id, messages = ChatService().list_history(
        db,
        student_user=student_user,
        agent_type=agent_type,
        subject_code=subject_code,
    )
    return ChatHistoryOut(
        session_id=session_id,
        messages=[ChatHistoryMessageOut(**row) for row in messages],
    )


@router.post("/chat", response_model=ChatPostResponse)
def post_chat(
    payload: ChatPostRequest,
    db: Session = Depends(get_db),
    student_user: User = Depends(require_student),
) -> ChatPostResponse:
    session_id, assistant_message, tools_used = ChatService().post_message(
        db,
        student_user=student_user,
        agent_type=payload.agent_type,
        subject_code=payload.subject_code,
        message=payload.message,
    )
    return ChatPostResponse(
        session_id=session_id,
        assistant_message=assistant_message,
        tools_used=tools_used,
    )

