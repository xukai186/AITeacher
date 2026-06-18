import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PastExamQuestion(Base):
    """往年真题片段，供摸底组卷参考题型与难度。"""

    __tablename__ = "past_exam_questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    subject_code: Mapped[str] = mapped_column(String(40), nullable=False)
    source_year: Mapped[int] = mapped_column(Integer, nullable=False)
    syllabus_exam_year: Mapped[int] = mapped_column(Integer, nullable=False)

    knowledge_node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("syllabus_nodes.id", ondelete="SET NULL"), nullable=True
    )

    q_type: Mapped[str] = mapped_column(String(40), nullable=False, default="single_choice")
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    choices_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    answer_key: Mapped[str] = mapped_column(String(8), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
