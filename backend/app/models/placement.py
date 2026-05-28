import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PlacementPaper(Base):
    __tablename__ = "placement_papers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    subject_code: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="ready")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PlacementQuestion(Base):
    __tablename__ = "placement_questions"
    __table_args__ = (
        UniqueConstraint("paper_id", "seq", name="uq_placement_question_seq_per_paper"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    paper_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("placement_papers.id", ondelete="CASCADE"), nullable=False
    )

    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    knowledge_node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("syllabus_nodes.id", ondelete="SET NULL"), nullable=True
    )
    q_type: Mapped[str] = mapped_column(String(40), nullable=False, default="single_choice")
    stem: Mapped[str] = mapped_column(String, nullable=False)
    choices_json: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    answer_key: Mapped[str] = mapped_column(String(40), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

