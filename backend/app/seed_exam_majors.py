"""Seed exam major categories and majors for placement and planning."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ExamMajor, ExamMajorCategory

_CATEGORIES: list[dict] = [
    {"code": "academic_master", "name": "学硕", "sort_order": 1},
    {"code": "professional_master", "name": "专硕", "sort_order": 2},
    {"code": "management_joint", "name": "管理类联考", "sort_order": 3},
]

_MAJORS: list[dict] = [
    # 学硕 — 英一 + 数一
    {
        "code": "cs_academic",
        "category_code": "academic_master",
        "name": "计算机科学与技术",
        "default_english_track": "english_1",
        "default_math_track": "math_1",
        "default_subject_codes": ["english", "math", "politics"],
        "notes": None,
    },
    {
        "code": "software_academic",
        "category_code": "academic_master",
        "name": "软件工程",
        "default_english_track": "english_1",
        "default_math_track": "math_1",
        "default_subject_codes": ["english", "math", "politics"],
        "notes": None,
    },
    {
        "code": "ee_academic",
        "category_code": "academic_master",
        "name": "电子科学与技术",
        "default_english_track": "english_1",
        "default_math_track": "math_1",
        "default_subject_codes": ["english", "math", "politics"],
        "notes": None,
    },
    {
        "code": "me_academic",
        "category_code": "academic_master",
        "name": "机械工程",
        "default_english_track": "english_1",
        "default_math_track": "math_1",
        "default_subject_codes": ["english", "math", "politics"],
        "notes": None,
    },
    {
        "code": "automation_academic",
        "category_code": "academic_master",
        "name": "控制科学与工程",
        "default_english_track": "english_1",
        "default_math_track": "math_1",
        "default_subject_codes": ["english", "math", "politics"],
        "notes": None,
    },
    {
        "code": "math_academic",
        "category_code": "academic_master",
        "name": "数学",
        "default_english_track": "english_1",
        "default_math_track": "math_1",
        "default_subject_codes": ["english", "math", "politics"],
        "notes": None,
    },
    {
        "code": "physics_academic",
        "category_code": "academic_master",
        "name": "物理学",
        "default_english_track": "english_1",
        "default_math_track": "math_1",
        "default_subject_codes": ["english", "math", "politics"],
        "notes": None,
    },
    {
        "code": "chemistry_academic",
        "category_code": "academic_master",
        "name": "化学",
        "default_english_track": "english_1",
        "default_math_track": "math_1",
        "default_subject_codes": ["english", "math", "politics"],
        "notes": None,
    },
    {
        "code": "biology_academic",
        "category_code": "academic_master",
        "name": "生物学",
        "default_english_track": "english_1",
        "default_math_track": "math_1",
        "default_subject_codes": ["english", "math", "politics"],
        "notes": None,
    },
    {
        "code": "economics_academic",
        "category_code": "academic_master",
        "name": "理论经济学",
        "default_english_track": "english_1",
        "default_math_track": "math_1",
        "default_subject_codes": ["english", "math", "politics"],
        "notes": None,
    },
    {
        "code": "management_science_academic",
        "category_code": "academic_master",
        "name": "管理科学与工程",
        "default_english_track": "english_1",
        "default_math_track": "math_1",
        "default_subject_codes": ["english", "math", "politics"],
        "notes": None,
    },
    # 专硕 — 常见英二 + 数二
    {
        "code": "accounting_prof",
        "category_code": "professional_master",
        "name": "会计",
        "default_english_track": "english_2",
        "default_math_track": "math_2",
        "default_subject_codes": ["english", "math", "politics"],
        "notes": None,
    },
    {
        "code": "law_prof",
        "category_code": "professional_master",
        "name": "法律",
        "default_english_track": "english_1",
        "default_math_track": "none",
        "default_subject_codes": ["english", "politics"],
        "notes": "法律硕士（非法学）通常不考数学",
    },
    {
        "code": "finance_prof",
        "category_code": "professional_master",
        "name": "金融",
        "default_english_track": "english_2",
        "default_math_track": "math_3",
        "default_subject_codes": ["english", "math", "politics"],
        "notes": None,
    },
    {
        "code": "translation_prof",
        "category_code": "professional_master",
        "name": "翻译",
        "default_english_track": "english_1",
        "default_math_track": "none",
        "default_subject_codes": ["english", "politics"],
        "notes": None,
    },
    {
        "code": "education_prof",
        "category_code": "professional_master",
        "name": "教育",
        "default_english_track": "english_2",
        "default_math_track": "none",
        "default_subject_codes": ["english", "politics"],
        "notes": None,
    },
    {
        "code": "journalism_prof",
        "category_code": "professional_master",
        "name": "新闻与传播",
        "default_english_track": "english_2",
        "default_math_track": "none",
        "default_subject_codes": ["english", "politics"],
        "notes": None,
    },
    {
        "code": "social_work_prof",
        "category_code": "professional_master",
        "name": "社会工作",
        "default_english_track": "english_2",
        "default_math_track": "none",
        "default_subject_codes": ["english", "politics"],
        "notes": None,
    },
    {
        "code": "architecture_prof",
        "category_code": "professional_master",
        "name": "建筑学",
        "default_english_track": "english_1",
        "default_math_track": "math_1",
        "default_subject_codes": ["english", "math", "politics"],
        "notes": None,
    },
    {
        "code": "clinical_medicine_prof",
        "category_code": "professional_master",
        "name": "临床医学",
        "default_english_track": "english_1",
        "default_math_track": "none",
        "default_subject_codes": ["english", "politics"],
        "notes": None,
    },
    {
        "code": "electronic_info_prof",
        "category_code": "professional_master",
        "name": "电子信息",
        "default_english_track": "english_1",
        "default_math_track": "math_1",
        "default_subject_codes": ["english", "math", "politics"],
        "notes": None,
    },
    {
        "code": "nursing_prof",
        "category_code": "professional_master",
        "name": "护理",
        "default_english_track": "english_2",
        "default_math_track": "none",
        "default_subject_codes": ["english", "politics"],
        "notes": None,
    },
    # 管理类联考 — 英二 + 无数学
    {
        "code": "mba_joint",
        "category_code": "management_joint",
        "name": "工商管理（MBA）",
        "default_english_track": "english_2",
        "default_math_track": "none",
        "default_subject_codes": ["english", "politics"],
        "notes": "管理类联考综合能力替代数学",
    },
    {
        "code": "mpacc_joint",
        "category_code": "management_joint",
        "name": "会计（MPAcc）",
        "default_english_track": "english_2",
        "default_math_track": "none",
        "default_subject_codes": ["english", "politics"],
        "notes": None,
    },
    {
        "code": "mem_joint",
        "category_code": "management_joint",
        "name": "工程管理（MEM）",
        "default_english_track": "english_2",
        "default_math_track": "none",
        "default_subject_codes": ["english", "politics"],
        "notes": None,
    },
    {
        "code": "mpa_joint",
        "category_code": "management_joint",
        "name": "公共管理（MPA）",
        "default_english_track": "english_2",
        "default_math_track": "none",
        "default_subject_codes": ["english", "politics"],
        "notes": None,
    },
    {
        "code": "mlis_joint",
        "category_code": "management_joint",
        "name": "图书情报（MLIS）",
        "default_english_track": "english_2",
        "default_math_track": "none",
        "default_subject_codes": ["english", "politics"],
        "notes": None,
    },
    {
        "code": "mta_joint",
        "category_code": "management_joint",
        "name": "旅游管理（MTA）",
        "default_english_track": "english_2",
        "default_math_track": "none",
        "default_subject_codes": ["english", "politics"],
        "notes": None,
    },
    {
        "code": "maud_joint",
        "category_code": "management_joint",
        "name": "审计（MAud）",
        "default_english_track": "english_2",
        "default_math_track": "none",
        "default_subject_codes": ["english", "politics"],
        "notes": None,
    },
]


def seed_exam_majors(db: Session) -> None:
    for spec in _CATEGORIES:
        existing = db.get(ExamMajorCategory, spec["code"])
        if existing is not None:
            existing.name = spec["name"]
            existing.sort_order = spec["sort_order"]
            continue
        db.add(ExamMajorCategory(**spec))

    db.flush()

    for spec in _MAJORS:
        existing = db.get(ExamMajor, spec["code"])
        if existing is not None:
            existing.category_code = spec["category_code"]
            existing.name = spec["name"]
            existing.default_english_track = spec["default_english_track"]
            existing.default_math_track = spec["default_math_track"]
            existing.default_subject_codes = spec["default_subject_codes"]
            existing.notes = spec["notes"]
            continue
        db.add(ExamMajor(**spec))

    db.flush()
