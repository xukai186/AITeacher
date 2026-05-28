"""Seed a minimal 2-level syllabus tree for P3 placement and planning."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import SyllabusNode

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
    db: Session, subject_code: str, parent_id, name: str
) -> SyllabusNode | None:
    stmt = select(SyllabusNode).where(
        SyllabusNode.subject_code == subject_code,
        SyllabusNode.name == name,
    )
    if parent_id is None:
        stmt = stmt.where(SyllabusNode.parent_id.is_(None))
    else:
        stmt = stmt.where(SyllabusNode.parent_id == parent_id)
    return db.execute(stmt).scalar_one_or_none()


def _ensure_node(
    db: Session, subject_code: str, parent_id, name: str, weight: int
) -> SyllabusNode:
    existing = _find_node(db, subject_code, parent_id, name)
    if existing is not None:
        return existing
    node = SyllabusNode(
        subject_code=subject_code,
        parent_id=parent_id,
        name=name,
        weight=weight,
    )
    db.add(node)
    db.flush()
    return node


def seed_minimal_syllabus(db: Session) -> None:
    for subject_code, (root_title, children) in _MINIMAL_SYLLABUS.items():
        root = _ensure_node(db, subject_code, None, root_title, weight=1)
        for child_name in children:
            _ensure_node(db, subject_code, root.id, child_name, weight=1)


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
