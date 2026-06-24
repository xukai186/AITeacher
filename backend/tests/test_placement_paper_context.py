from app.auth.security import hash_password
from app.models import PastExamPaperTemplate, StudentProfile, UserRole
from app.seed_syllabus import seed_minimal_syllabus
from app.services.placement_paper_context import (
    build_placement_context,
    build_placement_slots,
    leaf_nodes_for_placement,
    resolve_placement_question_count,
)
from tests.factories import make_org, make_user


def test_build_placement_context_uses_full_exam_counts(db_session):
    org = make_org(db_session)
    student = make_user(
        db_session,
        org,
        role=UserRole.student,
        email="ctx@demo.example",
        password_hash=hash_password("pw"),
    )
    seed_minimal_syllabus(db_session)
    db_session.add(StudentProfile(user_id=student.id, exam_year=2027))
    db_session.commit()

    ctx = build_placement_context(
        db_session,
        student_user_id=student.id,
        subject_code="math",
    )

    assert sum(section["count"] for section in ctx.paper_sections) == 22
    assert resolve_placement_question_count(
        db_session, subject_code="math", student_user_id=student.id
    ) == 22


def test_build_placement_slots_include_non_choice_types(db_session):
    org = make_org(db_session)
    student = make_user(
        db_session,
        org,
        role=UserRole.student,
        email="slots@demo.example",
        password_hash=hash_password("pw"),
    )
    seed_minimal_syllabus(db_session)
    db_session.add(StudentProfile(user_id=student.id, exam_year=2027))
    db_session.commit()

    ctx = build_placement_context(
        db_session,
        student_user_id=student.id,
        subject_code="math",
    )
    leaves = leaf_nodes_for_placement(
        db_session, subject_code="math", exam_year=ctx.exam_year
    )
    slots = build_placement_slots(db_session, ctx, leaves, [])

    assert len(slots) == 22
    assert slots[0].q_type == "single_choice"
    assert slots[9].q_type == "single_choice"
    assert slots[10].q_type == "fill_blank"
    assert slots[15].q_type == "fill_blank"
    assert slots[16].q_type == "short_answer"
    assert slots[0].points == 4
    assert slots[16].points == 10


def test_load_template_prefers_english_2_track(db_session):
    org = make_org(db_session)
    student = make_user(
        db_session,
        org,
        role=UserRole.student,
        email="english2@demo.example",
        password_hash=hash_password("pw"),
    )
    db_session.add(StudentProfile(user_id=student.id, exam_year=2027))

    db_session.add(
        PastExamPaperTemplate(
            subject_code="english",
            syllabus_exam_year=2027,
            reference_year=2024,
            title="英语模拟摸底卷（参照2024年英语一真题题型与题量）",
            english_track="english_1",
            math_track=None,
            sections_json=[
                {"section_name": "阅读理解A", "q_type": "single_choice", "count": 20, "knowledge_area": "阅读", "points": 2}
            ],
        )
    )
    db_session.add(
        PastExamPaperTemplate(
            subject_code="english",
            syllabus_exam_year=2027,
            reference_year=2024,
            title="英语二模拟摸底卷（参照2024年英语二真题题型与题量）",
            english_track="english_2",
            math_track=None,
            sections_json=[
                {"section_name": "阅读理解A", "q_type": "single_choice", "count": 15, "knowledge_area": "阅读", "points": 2}
            ],
        )
    )
    db_session.commit()

    ctx = build_placement_context(
        db_session,
        student_user_id=student.id,
        subject_code="english",
        english_track="english_2",
    )

    assert ctx.paper_title == "英语二模拟摸底卷（参照2024年英语二真题题型与题量）"
    assert sum(section["count"] for section in ctx.paper_sections) == 15
