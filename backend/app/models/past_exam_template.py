import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PastExamPaperTemplate(Base):
    """往年真题卷结构模板：题型、题量、板块划分，供摸底模拟卷组卷。"""

    __tablename__ = "past_exam_paper_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    subject_code: Mapped[str] = mapped_column(String(40), nullable=False)
    syllabus_exam_year: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_year: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)

    sections_json: Mapped[list] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
