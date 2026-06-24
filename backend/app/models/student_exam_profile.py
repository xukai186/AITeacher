import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class StudentExamProfile(Base):
    __tablename__ = "student_exam_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    major_category_code: Mapped[str] = mapped_column(
        String(60), ForeignKey("exam_major_categories.code"), nullable=False
    )
    major_code: Mapped[str] = mapped_column(
        String(60), ForeignKey("exam_majors.code"), nullable=False
    )
    english_track: Mapped[str | None] = mapped_column(String(20), nullable=True)
    math_track: Mapped[str | None] = mapped_column(String(20), nullable=True)
    subject_codes: Mapped[list] = mapped_column(JSONB, nullable=False)
    cet_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cet_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    math_mastery_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    profile_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
