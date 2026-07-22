"""Seed a minimal 3-level syllabus tree for P3 placement and planning."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import SyllabusNode
from app.seed_past_exams import seed_past_exam_questions
from app.seed_past_exam_templates import seed_past_exam_paper_templates

DEFAULT_SYLLABUS_EXAM_YEAR = 2027

# subject -> (root, [(l1_name, meta, [leaf_names...]), ...])
_MINIMAL_SYLLABUS: dict[str, tuple[str, list[tuple[str, dict | None, list[str]]]]] = {
    "english": (
        "英语",
        [
            (
                "阅读",
                None,
                [
                    "细节题",
                    "主旨题",
                    "推断题",
                    "态度题",
                    "词汇题",
                    "例证题",
                    "篇章结构",
                    "长难句",
                ],
            ),
            (
                "翻译",
                None,
                [
                    "词义选择",
                    "长句拆分",
                    "定语从句译",
                    "被动语态译",
                    "名词性从句译",
                    "状语从句译",
                    "增译减译",
                    "语序调整",
                ],
            ),
            (
                "写作",
                None,
                [
                    "图表描述",
                    "图画寓意",
                    "开头段",
                    "中间论证",
                    "结尾段",
                    "连接词",
                    "应用文格式",
                    "书信请求",
                ],
            ),
        ],
    ),
    "math": (
        "数学",
        [
            (
                "高数",
                {"tracks": ["math_1"]},
                ["极限", "连续", "导数", "微分", "不定积分", "定积分", "微分方程", "多元函数"],
            ),
            (
                "线代",
                None,
                ["行列式", "矩阵运算", "逆矩阵", "线性方程组", "向量组", "特征值", "二次型", "相似对角化"],
            ),
            (
                "概率",
                None,
                ["随机事件", "条件概率", "随机变量", "分布函数", "期望方差", "常见分布", "大数定律", "中心极限"],
            ),
        ],
    ),
    "politics": (
        "政治",
        [
            (
                "马原",
                None,
                ["唯物论", "辩证法", "认识论", "唯物史观", "实践观", "矛盾规律", "否定之否定", "量变质变"],
            ),
            (
                "毛中特",
                None,
                ["新民主主义", "社会主义改造", "改革开放", "市场经济", "一国两制", "三个代表", "科学发展观", "中国特色"],
            ),
            (
                "史纲",
                None,
                ["鸦片战争", "辛亥革命", "五四运动", "建党", "长征", "抗战", "解放战争", "建国初期"],
            ),
            (
                "思修",
                None,
                ["理想信念", "中国精神", "人生价值", "道德规范", "法治思维", "宪法法律", "权利义务", "社会责任"],
            ),
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
    meta_json: dict | None = None,
) -> SyllabusNode:
    existing = _find_node(db, subject_code, parent_id, name, exam_year)
    if existing is not None:
        if exam_year is not None and existing.exam_year is None:
            existing.exam_year = exam_year
            db.flush()
        if meta_json is not None and existing.meta_json != meta_json:
            existing.meta_json = meta_json
            db.flush()
        return existing
    node = SyllabusNode(
        subject_code=subject_code,
        parent_id=parent_id,
        name=name,
        weight=weight,
        exam_year=exam_year,
        meta_json=meta_json,
    )
    db.add(node)
    db.flush()
    return node


def seed_minimal_syllabus(db: Session, *, exam_year: int = DEFAULT_SYLLABUS_EXAM_YEAR) -> None:
    for subject_code, (root_title, chapters) in _MINIMAL_SYLLABUS.items():
        root = _ensure_node(db, subject_code, None, root_title, weight=1, exam_year=exam_year)
        for chapter_name, chapter_meta, leaf_names in chapters:
            chapter = _ensure_node(
                db,
                subject_code,
                root.id,
                chapter_name,
                weight=1,
                exam_year=exam_year,
                meta_json=chapter_meta,
            )
            for leaf_name in leaf_names:
                _ensure_node(
                    db,
                    subject_code,
                    chapter.id,
                    leaf_name,
                    weight=1,
                    exam_year=exam_year,
                    meta_json=chapter_meta,
                )
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
