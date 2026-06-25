from sqlalchemy import func, select

from app.models import ExamMajor, ExamMajorCategory


def test_seed_exam_majors_populates_categories(db_session):
    from app.seed_exam_majors import seed_exam_majors

    seed_exam_majors(db_session)
    db_session.commit()

    cats = db_session.execute(select(ExamMajorCategory)).scalars().all()
    assert {c.code for c in cats} >= {
        "academic_master",
        "professional_master",
        "management_joint",
    }

    majors = db_session.execute(select(ExamMajor)).scalars().all()
    assert len(majors) >= 20


def test_seed_exam_majors_idempotent(db_session):
    from app.seed_exam_majors import seed_exam_majors

    seed_exam_majors(db_session)
    db_session.commit()
    cat_count = db_session.execute(select(func.count()).select_from(ExamMajorCategory)).scalar_one()
    major_count = db_session.execute(select(func.count()).select_from(ExamMajor)).scalar_one()

    seed_exam_majors(db_session)
    db_session.commit()

    assert (
        db_session.execute(select(func.count()).select_from(ExamMajorCategory)).scalar_one()
        == cat_count
    )
    assert (
        db_session.execute(select(func.count()).select_from(ExamMajor)).scalar_one() == major_count
    )
