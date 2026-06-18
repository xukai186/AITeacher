"""Seed a minimal 2-level syllabus tree for P3 placement and planning."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import SyllabusNode
from app.seed_past_exams import seed_past_exam_questions
from app.seed_past_exam_templates import seed_past_exam_paper_templates

DEFAULT_SYLLABUS_EXAM_YEAR = 2027

# subject_code -> (root name, [child names...])
_MINIMAL_SYLLABUS: dict[str, tuple[str, list[str]]] = {
    "english": ("英语", ["阅读", "翻译", "写作"]),
    "math": ("数学", ["高数", "线代", "概率"]),
    "politics": (
        "政治",
        [
            "马原",
            "毛中特",
            "史纲",
            "思修",
        ],
    ),
}


def _find_node(
    db: Session,
    subject_code: str,
    parent_id,
    name: str,
    exam_year: int | None,
) -> SyllabusNode | None:
    stmt = select(SyllabusNode).where(
        SyllabusNode.subject_code == subject_code,
        SyllabusNode.name == name,
    )
    if parent_id is None:
        stmt = stmt.where(SyllabusNode.parent_id.is_(None))
    else:
        stmt = stmt.where(SyllabusNode.parent_id == parent_id)
    candidates = list(db.execute(stmt).scalars().all())
    if not candidates:
        return None
    if exam_year is not None:
        for node in candidates:
            if node.exam_year == exam_year:
                return node
        for node in candidates:
            if node.exam_year is None:
                return node
        return None
    for node in candidates:
        if node.exam_year is None:
            return node
    return candidates[0]


def _ensure_node(
    db: Session,
    subject_code: str,
    parent_id,
    name: str,
    weight: int,
    exam_year: int | None = DEFAULT_SYLLABUS_EXAM_YEAR,
) -> SyllabusNode:
    existing = _find_node(db, subject_code, parent_id, name, exam_year)
    if existing is not None:
        if exam_year is not None and existing.exam_year is None:
            existing.exam_year = exam_year
            db.flush()
        return existing
    node = SyllabusNode(
        subject_code=subject_code,
        parent_id=parent_id,
        name=name,
        weight=weight,
        exam_year=exam_year,
    )
    db.add(node)
    db.flush()
    return node


def seed_minimal_syllabus(db: Session, *, exam_year: int = DEFAULT_SYLLABUS_EXAM_YEAR) -> None:
    for subject_code, (root_title, children) in _MINIMAL_SYLLABUS.items():
        root = _ensure_node(db, subject_code, None, root_title, weight=1, exam_year=exam_year)
        for child_name in children:
            _ensure_node(db, subject_code, root.id, child_name, weight=1, exam_year=exam_year)
    seed_past_exam_questions(db, syllabus_exam_year=exam_year)
    seed_past_exam_paper_templates(db, syllabus_exam_year=exam_year)


def main() -> None:
    db = SessionLocal()
    try:
        seed_minimal_syllabus(db)
        db.commit()
        print("Syllabus seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
