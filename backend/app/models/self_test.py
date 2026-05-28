import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SelfTestPaper(Base):
    __tablename__ = "self_test_papers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    subject_code: Mapped[str] = mapped_column(String(40), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="ai")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="ready")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SelfTestQuestion(Base):
    __tablename__ = "self_test_questions"
    __table_args__ = (
        UniqueConstraint("paper_id", "seq", name="uq_self_test_question_seq_per_paper"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    paper_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("self_test_papers.id", ondelete="CASCADE"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)

    knowledge_node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("syllabus_nodes.id", ondelete="SET NULL"), nullable=True
    )
    q_type: Mapped[str] = mapped_column(String(40), nullable=False, default="single_choice")
    stem: Mapped[str] = mapped_column(String, nullable=False)
    choices_json: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    answer_key: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    rubric_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SelfTestSubmission(Base):
    __tablename__ = "self_test_submissions"
    __table_args__ = (
        UniqueConstraint("paper_id", "student_user_id", name="uq_self_test_submission_paper_student"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    paper_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("self_test_papers.id", ondelete="CASCADE"), nullable=False
    )
    student_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="submitted")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SelfTestAnswer(Base):
    __tablename__ = "self_test_answers"
    __table_args__ = (
        UniqueConstraint(
            "submission_id",
            "question_id",
            name="uq_self_test_answer_submission_question",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("self_test_submissions.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("self_test_questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(String(8000), nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SelfTestGrade(Base):
    __tablename__ = "self_test_grades"
    __table_args__ = (
        UniqueConstraint("submission_id", name="uq_self_test_grade_submission"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("self_test_submissions.id", ondelete="CASCADE"),
        nullable=False,
    )
    total_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    detail_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

