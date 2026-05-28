from sqlalchemy import select

from app.models import SyllabusNode
from app.seed_syllabus import seed_minimal_syllabus


def test_seed_minimal_syllabus_idempotent(db_session):
    seed_minimal_syllabus(db_session)
    seed_minimal_syllabus(db_session)
    rows = db_session.execute(select(SyllabusNode)).scalars().all()
    assert len(rows) > 0
