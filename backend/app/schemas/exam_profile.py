from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

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
