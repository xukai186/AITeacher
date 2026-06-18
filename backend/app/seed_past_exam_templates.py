"""Seed past exam paper templates (题型与题量) for placement mock papers."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PastExamPaperTemplate

# 参照近年真题卷结构，题量为摸底场景下的精简比例（板块与题型保持一致）
_PLACEMENT_MOCK_TEMPLATES: dict[str, dict] = {
    "english": {
        "reference_year": 2024,
        "title": "英语模拟摸底卷（参照2024年真题题型与题量）",
        "sections": [
            {"section_name": "完形填空", "q_type": "single_choice", "count": 2, "knowledge_area": "阅读"},
            {"section_name": "阅读理解", "q_type": "single_choice", "count": 4, "knowledge_area": "阅读"},
            {"section_name": "翻译", "q_type": "single_choice", "count": 2, "knowledge_area": "翻译"},
            {"section_name": "写作", "q_type": "single_choice", "count": 2, "knowledge_area": "写作"},
        ],
    },
    "math": {
        "reference_year": 2024,
        "title": "数学模拟摸底卷（参照2024年真题题型与题量）",
        "sections": [
            {"section_name": "选择题", "q_type": "single_choice", "count": 6, "knowledge_area": "高数"},
            {"section_name": "填空题", "q_type": "single_choice", "count": 2, "knowledge_area": "线代"},
            {"section_name": "解答题", "q_type": "single_choice", "count": 2, "knowledge_area": "概率"},
        ],
    },
    "politics": {
        "reference_year": 2024,
        "title": "政治模拟摸底卷（参照2024年真题题型与题量）",
        "sections": [
            {"section_name": "单项选择题", "q_type": "single_choice", "count": 8, "knowledge_area": "马原"},
            {"section_name": "多项选择题", "q_type": "multiple_choice", "count": 2, "knowledge_area": "史纲"},
        ],
    },
}


def seed_past_exam_paper_templates(db: Session, *, syllabus_exam_year: int = 2027) -> None:
    for subject_code, spec in _PLACEMENT_MOCK_TEMPLATES.items():
        exists = db.execute(
            select(PastExamPaperTemplate.id).where(
                PastExamPaperTemplate.subject_code == subject_code,
                PastExamPaperTemplate.syllabus_exam_year == syllabus_exam_year,
            )
        ).scalar_one_or_none()
        if exists is not None:
            continue
        db.add(
            PastExamPaperTemplate(
                subject_code=subject_code,
                syllabus_exam_year=syllabus_exam_year,
                reference_year=spec["reference_year"],
                title=spec["title"],
                sections_json=spec["sections"],
            )
        )
    db.flush()


def placement_question_count_for_subject(subject_code: str) -> int:
    spec = _PLACEMENT_MOCK_TEMPLATES.get(subject_code)
    if spec is None:
        return 10
    return sum(section["count"] for section in spec["sections"])
