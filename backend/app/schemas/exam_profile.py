from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EnglishTrack = Literal["english_1", "english_2"]
MathTrack = Literal["math_1", "math_2", "none"]
CetStatus = Literal["not_taken", "cet4", "cet6"]
MathMasteryLevel = Literal["zero", "basic", "good", "strong"]


@dataclass(frozen=True)
class EffectiveExamProfile:
    major_category_code: str
    major_code: str
    major_name: str
    english_track: EnglishTrack
    math_track: MathTrack
    subject_codes: list[str]
    cet_status: CetStatus | None
    cet_score: int | None
    math_mastery_level: MathMasteryLevel | None
    profile_completed_at: datetime | None


class ExamMajorCategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    sort_order: int


class ExamMajorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    category_code: str
    name: str
    default_english_track: EnglishTrack
    default_math_track: MathTrack
    default_subject_codes: list[str]
    notes: str | None = None


class ExamProfileIn(BaseModel):
    major_category_code: str = Field(min_length=1, max_length=60)
    major_code: str = Field(min_length=1, max_length=60)
    english_track: EnglishTrack | None = None
    math_track: MathTrack | None = None
    subject_codes: list[str] | None = None
    cet_status: CetStatus | None = None
    cet_score: int | None = Field(default=None, ge=0)
    math_mastery_level: MathMasteryLevel | None = None


class ExamProfileOut(BaseModel):
    major_category_code: str
    major_code: str
    major_name: str
    english_track: EnglishTrack | None = None
    math_track: MathTrack | None = None
    effective_english_track: EnglishTrack
    effective_math_track: MathTrack
    subject_codes: list[str]
    cet_status: CetStatus | None = None
    cet_score: int | None = None
    math_mastery_level: MathMasteryLevel | None = None
    profile_completed_at: datetime | None = None
    is_complete: bool
