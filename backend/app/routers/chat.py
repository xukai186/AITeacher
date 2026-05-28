from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.permissions import require_roles
from app.database import get_db
from app.models import User, UserRole
from app.schemas.chat import ChatPostRequest, ChatPostResponse
from app.services.chat import ChatService

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatPostResponse)
def post_chat(
    payload: ChatPostRequest,
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
) -> ChatPostResponse:
    session_id, assistant_message = ChatService().post_message(
        db,
        student_user=student,
        agent_type=payload.agent_type,
        subject_code=payload.subject_code,
        message=payload.message,
    )
    return ChatPostResponse(session_id=session_id, assistant_message=assistant_message)

