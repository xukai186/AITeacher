"""Seed a minimal 2-level syllabus tree for P3 placement and planning."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import SyllabusNode

# subject_code -> (root title, [(child title, child code), ...])
_MINIMAL_SYLLABUS: dict[str, tuple[str, list[tuple[str, str]]]] = {
    "english": ("英语", [("阅读", "reading"), ("翻译", "translation"), ("写作", "writing")]),
    "math": ("数学", [("高数", "calculus"), ("线代", "linear_algebra"), ("概率", "probability")]),
    "politics": (
        "政治",
        [
            ("马原", "marxism"),
            ("毛中特", "mao_thought"),
            ("史纲", "history"),
            ("思修", "ethics"),
        ],
    ),
}


def _find_node(
    db: Session, subject_code: str, parent_id, title: str
) -> SyllabusNode | None:
    stmt = select(SyllabusNode).where(
        SyllabusNode.subject_code == subject_code,
        SyllabusNode.title == title,
    )
    if parent_id is None:
        stmt = stmt.where(SyllabusNode.parent_id.is_(None))
    else:
        stmt = stmt.where(SyllabusNode.parent_id == parent_id)
    return db.execute(stmt).scalar_one_or_none()


def _ensure_node(
    db: Session, subject_code: str, parent_id, title: str, code: str
) -> SyllabusNode:
    existing = _find_node(db, subject_code, parent_id, title)
    if existing is not None:
        return existing
    node = SyllabusNode(
        subject_code=subject_code,
        parent_id=parent_id,
        title=title,
        code=code,
    )
    db.add(node)
    db.flush()
    return node


def seed_minimal_syllabus(db: Session) -> None:
    for subject_code, (root_title, children) in _MINIMAL_SYLLABUS.items():
        root = _ensure_node(db, subject_code, None, root_title, subject_code)
        for child_title, child_code in children:
            _ensure_node(
                db,
                subject_code,
                root.id,
                child_title,
                f"{subject_code}.{child_code}",
            )


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
