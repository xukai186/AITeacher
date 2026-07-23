"""Seed minimal past exam questions for placement paper generation."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PastExamQuestion, SyllabusNode

# subject -> [(leaf_name, source_year, stem, choices, answer_key), ...]
_SAMPLE_PAST_EXAMS: dict[str, list[tuple[int, str, str, list[dict], str]]] = {
    "english": [
        (
            2024,
            "主旨题",
            "【2024真题·阅读】According to the passage, the author mainly argues that…",
            [
                {"key": "A", "text": "technology alone cannot solve social problems"},
                {"key": "B", "text": "education reform is unnecessary"},
                {"key": "C", "text": "economic growth guarantees fairness"},
                {"key": "D", "text": "tradition should be abandoned entirely"},
            ],
            "A",
        ),
        (
            2023,
            "词义选择",
            "【2023真题·翻译】将下列句子译为英文：随着人工智能的发展，教育方式正在发生深刻变化。",
            [
                {"key": "A", "text": "With the development of AI, education is changing deeply."},
                {"key": "B", "text": "AI development has no impact on education."},
                {"key": "C", "text": "Education will never change because of technology."},
                {"key": "D", "text": "Only schools can adopt new teaching methods."},
            ],
            "A",
        ),
    ],
    "math": [
        (
            2024,
            "导数",
            "【2024真题·高数】设函数 f(x)=x^2 ln x，则 f'(1) 等于（  ）",
            [
                {"key": "A", "text": "0"},
                {"key": "B", "text": "1"},
                {"key": "C", "text": "2"},
                {"key": "D", "text": "e"},
            ],
            "B",
        ),
        (
            2023,
            "行列式",
            "【2023真题·线代】已知矩阵 A 为 2 阶可逆矩阵，则 |2A| 等于（  ）",
            [
                {"key": "A", "text": "2|A|"},
                {"key": "B", "text": "4|A|"},
                {"key": "C", "text": "|A|/2"},
                {"key": "D", "text": "|A|^2"},
            ],
            "B",
        ),
    ],
    "politics": [
        (
            2024,
            "实践观",
            "【2024真题·马原】实践是检验真理的唯一标准，这一论断体现了（  ）",
            [
                {"key": "A", "text": "认识对实践的决定作用"},
                {"key": "B", "text": "实践是认识的基础"},
                {"key": "C", "text": "真理具有绝对性"},
                {"key": "D", "text": "意识具有能动性"},
            ],
            "B",
        ),
        (
            2023,
            "五四运动",
            "【2023真题·史纲】新民主主义革命的开端是（  ）",
            [
                {"key": "A", "text": "辛亥革命"},
                {"key": "B", "text": "五四运动"},
                {"key": "C", "text": "中国共产党成立"},
                {"key": "D", "text": "抗日战争胜利"},
            ],
            "B",
        ),
    ],
}


def _find_leaf(db: Session, subject_code: str, leaf_name: str, exam_year: int) -> SyllabusNode | None:
    return db.execute(
        select(SyllabusNode).where(
            SyllabusNode.subject_code == subject_code,
            SyllabusNode.name == leaf_name,
            SyllabusNode.exam_year == exam_year,
        )
    ).scalars().first()


def seed_past_exam_questions(db: Session, *, syllabus_exam_year: int = 2027) -> None:
    for subject_code, items in _SAMPLE_PAST_EXAMS.items():
        for source_year, leaf_name, stem, choices, answer_key in items:
            node = _find_leaf(db, subject_code, leaf_name, syllabus_exam_year)
            exists = db.execute(
                select(PastExamQuestion.id).where(
                    PastExamQuestion.subject_code == subject_code,
                    PastExamQuestion.source_year == source_year,
                    PastExamQuestion.syllabus_exam_year == syllabus_exam_year,
                    PastExamQuestion.stem == stem,
                )
            ).scalar_one_or_none()
            if exists is not None:
                continue
            db.add(
                PastExamQuestion(
                    subject_code=subject_code,
                    source_year=source_year,
                    syllabus_exam_year=syllabus_exam_year,
                    knowledge_node_id=node.id if node else None,
                    q_type="single_choice",
                    stem=stem,
                    choices_json=choices,
                    answer_key=answer_key,
                )
            )
    db.flush()
