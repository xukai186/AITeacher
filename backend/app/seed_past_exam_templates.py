"""Seed past exam paper templates (题型与题量) for placement mock papers."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PastExamPaperTemplate

_PLACEMENT_MOCK_TEMPLATE_ROWS: list[dict] = [
    {
        "subject_code": "english",
        "english_track": "english_1",
        "math_track": None,
        "reference_year": 2024,
        "title": "英语模拟摸底卷（参照2024年英语一真题题型与题量）",
        "sections": [
            {"section_name": "完形填空", "q_type": "single_choice", "count": 20, "knowledge_area": "阅读", "points": 1},
            {"section_name": "阅读理解A", "q_type": "single_choice", "count": 20, "knowledge_area": "阅读", "points": 2},
            {"section_name": "阅读理解B", "q_type": "single_choice", "count": 5, "knowledge_area": "阅读", "points": 2},
            {"section_name": "翻译", "q_type": "short_answer", "count": 5, "knowledge_area": "翻译", "points": 2},
            {"section_name": "写作", "q_type": "essay", "count": 2, "knowledge_area": "写作", "points": 15},
        ],
    },
    {
        "subject_code": "english",
        "english_track": "english_2",
        "math_track": None,
        "reference_year": 2024,
        "title": "英语二模拟摸底卷（参照2024年英语二真题题型与题量）",
        "sections": [
            {"section_name": "完形填空", "q_type": "single_choice", "count": 20, "knowledge_area": "阅读", "points": 1},
            {"section_name": "阅读理解A", "q_type": "single_choice", "count": 20, "knowledge_area": "阅读", "points": 2},
            {"section_name": "阅读理解B", "q_type": "single_choice", "count": 5, "knowledge_area": "阅读", "points": 2},
            {"section_name": "翻译", "q_type": "short_answer", "count": 1, "knowledge_area": "翻译", "points": 15},
            {"section_name": "写作", "q_type": "essay", "count": 2, "knowledge_area": "写作", "points": 15},
        ],
    },
    {
        "subject_code": "math",
        "english_track": None,
        "math_track": "math_1",
        "reference_year": 2024,
        "title": "数学模拟摸底卷（参照2024年数学一真题题型与题量）",
        "sections": [
            {"section_name": "选择题", "q_type": "single_choice", "count": 10, "knowledge_area": "高数", "points": 4},
            {"section_name": "填空题", "q_type": "fill_blank", "count": 6, "knowledge_area": "线代", "points": 4},
            {"section_name": "解答题", "q_type": "short_answer", "count": 6, "knowledge_area": "概率", "points": 10},
        ],
    },
    {
        "subject_code": "math",
        "english_track": None,
        "math_track": "math_2",
        "reference_year": 2024,
        "title": "数学二模拟摸底卷（参照2024年数学二真题题型与题量）",
        "sections": [
            {"section_name": "选择题", "q_type": "single_choice", "count": 10, "knowledge_area": "高数", "points": 4},
            {"section_name": "填空题", "q_type": "fill_blank", "count": 6, "knowledge_area": "线代", "points": 4},
            {"section_name": "解答题", "q_type": "short_answer", "count": 6, "knowledge_area": "概率", "points": 10},
        ],
    },
    {
        "subject_code": "politics",
        "english_track": None,
        "math_track": None,
        "reference_year": 2024,
        "title": "政治模拟摸底卷（参照2024年政治真题题型与题量）",
        "sections": [
            {"section_name": "单项选择题", "q_type": "single_choice", "count": 16, "knowledge_area": "马原", "points": 1},
            {"section_name": "多项选择题", "q_type": "multi_choice", "count": 17, "knowledge_area": "史纲", "points": 2},
            {"section_name": "材料分析题", "q_type": "short_answer", "count": 5, "knowledge_area": "毛中特", "points": 10},
        ],
    },
]


def placement_question_count_for_subject(subject_code: str) -> int:
    for row in _PLACEMENT_MOCK_TEMPLATE_ROWS:
        if row["subject_code"] == subject_code:
            return sum(int(section["count"]) for section in row["sections"])
    return 10


def seed_past_exam_paper_templates(db: Session, *, syllabus_exam_year: int = 2027) -> None:
    for spec in _PLACEMENT_MOCK_TEMPLATE_ROWS:
        english_track = spec["english_track"]
        math_track = spec["math_track"]
        existing = db.execute(
            select(PastExamPaperTemplate).where(
                PastExamPaperTemplate.subject_code == spec["subject_code"],
                PastExamPaperTemplate.syllabus_exam_year == syllabus_exam_year,
                PastExamPaperTemplate.english_track.is_(None)
                if english_track is None
                else PastExamPaperTemplate.english_track == english_track,
                PastExamPaperTemplate.math_track.is_(None)
                if math_track is None
                else PastExamPaperTemplate.math_track == math_track,
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing.reference_year = spec["reference_year"]
            existing.title = spec["title"]
            existing.english_track = english_track
            existing.math_track = math_track
            existing.sections_json = spec["sections"]
            continue
        db.add(
            PastExamPaperTemplate(
                subject_code=spec["subject_code"],
                syllabus_exam_year=syllabus_exam_year,
                reference_year=spec["reference_year"],
                title=spec["title"],
                english_track=english_track,
                math_track=math_track,
                sections_json=spec["sections"],
            )
        )
    db.flush()
