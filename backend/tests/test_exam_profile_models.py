from sqlalchemy import select

from app.models import (
    ExamMajor,
    ExamMajorCategory,
    StudentExamProfile,
    UserRole,
)
from tests.factories import make_org, make_user


def test_exam_major_tables_exist(db_session):
    org = make_org(db_session)
    student = make_user(db_session, org, role=UserRole.student, email="exam-profile@demo.example")

    category = ExamMajorCategory(
        code="academic_master",
        name="学硕",
        sort_order=1,
    )
    db_session.add(category)
    db_session.flush()

    major = ExamMajor(
        code="cs_academic",
        category_code=category.code,
        name="计算机科学与技术",
        default_english_track="english_1",
        default_math_track="math_1",
        default_subject_codes=["english", "math", "politics"],
        notes=None,
    )
    db_session.add(major)
    db_session.flush()

    profile = StudentExamProfile(
        user_id=student.id,
        major_category_code=category.code,
        major_code=major.code,
        english_track="english_1",
        math_track="math_1",
        subject_codes=["english", "math", "politics"],
        cet_status="cet4",
        cet_score=520,
        math_mastery_level="basic",
    )
    db_session.add(profile)
    db_session.commit()

    assert db_session.get(ExamMajorCategory, "academic_master") is not None
    assert db_session.get(ExamMajor, "cs_academic") is not None
    assert db_session.get(StudentExamProfile, student.id) is not None

    result = db_session.execute(
        select(StudentExamProfile).where(StudentExamProfile.user_id == student.id)
    ).scalar_one()
    assert result.major_code == "cs_academic"
    assert result.subject_codes == ["english", "math", "politics"]
