from app.auth.security import hash_password
from app.models import StudentProfile, UserRole
from app.seed_syllabus import seed_minimal_syllabus
from app.services.placement_paper_context import (
    build_placement_context,
    build_placement_slots,
    leaf_nodes_for_placement,
    resolve_placement_paper_title,
    resolve_placement_question_count,
)
from tests.factories import make_org, make_user


def test_build_placement_context_includes_syllabus_and_past_exams(db_session):
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
        subject_code="english",
    )

    assert ctx.exam_year == 2027
    assert "2024" in ctx.paper_title
    assert len(ctx.syllabus_outline) >= 3
    assert any(item["parent_name"] == "英语" for item in ctx.syllabus_outline)
    assert len(ctx.past_exam_samples) >= 1
    assert any("2024真题" in s["stem"] for s in ctx.past_exam_samples)
    assert sum(section["count"] for section in ctx.paper_sections) == 10
    section_names = [section["section_name"] for section in ctx.paper_sections]
    assert section_names == ["完形填空", "阅读理解", "翻译", "写作"]


def test_build_placement_slots_follow_paper_template(db_session):
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
        subject_code="english",
    )
    leaves = leaf_nodes_for_placement(
        db_session, subject_code="english", exam_year=ctx.exam_year
    )
    slots = build_placement_slots(db_session, ctx, leaves, [])

    assert len(slots) == 10
    assert slots[0].section_name == "完形填空"
    assert slots[2].section_name == "阅读理解"
    assert slots[6].section_name == "翻译"
    assert resolve_placement_question_count(
        db_session, subject_code="english", student_user_id=student.id
    ) == 10
    assert "模拟摸底卷" in resolve_placement_paper_title(
        db_session, subject_code="english", student_user_id=student.id
    )
