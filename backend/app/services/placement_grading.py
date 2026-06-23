from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.services.grading import GradingService

OBJECTIVE_Q_TYPES = frozenset({"single_choice", "multi_choice", "fill_blank"})
SUBJECTIVE_Q_TYPES = frozenset({"short_answer", "essay"})


@dataclass(frozen=True)
class PlacementGradeableQuestion:
    q_type: str
    stem: str
    answer_key: str
    points: int
    rubric_json: dict | None = None


def normalize_student_answer(content: str, q_type: str) -> str:
    text = content.strip()
    if q_type == "multi_choice":
        letters = [c for c in text.upper() if c in "ABCD"]
        return "".join(sorted(set(letters)))
    if q_type == "fill_blank":
        return " ".join(text.split()).lower()
    return text


def normalize_answer_key(key: str, q_type: str) -> str:
    if q_type == "multi_choice":
        letters = [c for c in key.upper() if c in "ABCD"]
        return "".join(sorted(set(letters)))
    if q_type == "fill_blank":
        return " ".join((key or "").split()).lower()
    return (key or "").strip()


def grade_placement_answer(
    db: Session,
    *,
    org_id,
    question: PlacementGradeableQuestion,
    content: str,
) -> tuple[int, bool, dict | None]:
    q_type = question.q_type
    if q_type in OBJECTIVE_Q_TYPES:
        student = normalize_student_answer(content, q_type)
        expected = normalize_answer_key(question.answer_key, q_type)
        is_correct = bool(expected) and student == expected
        score = int(question.points) if is_correct else 0
        return score, is_correct, None

    if q_type in SUBJECTIVE_Q_TYPES:
        grader = GradingService()
        adapter = _SubjectiveAdapter(question)
        score, detail = grader.grade_subjective(db, org_id, adapter, content)
        is_correct = score >= max(1, int(question.points) // 2)
        return score, is_correct, detail

    student = content.strip()
    expected = (question.answer_key or "").strip()
    is_correct = bool(expected) and student == expected
    score = int(question.points) if is_correct else 0
    return score, is_correct, None


@dataclass
class _SubjectiveAdapter:
    q_type: str
    stem: str
    answer_key: str
    points: int
    rubric_json: dict | None

    def __init__(self, question: PlacementGradeableQuestion) -> None:
        self.q_type = question.q_type
        self.stem = question.stem
        self.answer_key = question.answer_key
        self.points = question.points
        self.rubric_json = question.rubric_json
