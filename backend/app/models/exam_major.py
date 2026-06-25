from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ExamMajorCategory(Base):
    __tablename__ = "exam_major_categories"

    code: Mapped[str] = mapped_column(String(60), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)


class ExamMajor(Base):
    __tablename__ = "exam_majors"

    code: Mapped[str] = mapped_column(String(60), primary_key=True)
    category_code: Mapped[str] = mapped_column(
        String(60), ForeignKey("exam_major_categories.code"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    default_english_track: Mapped[str] = mapped_column(String(20), nullable=False)
    default_math_track: Mapped[str] = mapped_column(String(20), nullable=False)
    default_subject_codes: Mapped[list] = mapped_column(JSONB, nullable=False)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
