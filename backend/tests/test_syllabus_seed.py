from sqlalchemy import select

from app.models import SyllabusNode
from app.seed_syllabus import seed_minimal_syllabus
from app.services.placement_paper_context import leaf_nodes_for_placement


def test_seed_minimal_syllabus_idempotent(db_session):
    seed_minimal_syllabus(db_session)
    seed_minimal_syllabus(db_session)
    rows = list(db_session.execute(select(SyllabusNode)).scalars().all())
    assert len(rows) > 0


def test_seed_has_eight_plus_leaves_per_l1(db_session):
    seed_minimal_syllabus(db_session)
    nodes = list(db_session.execute(select(SyllabusNode)).scalars().all())
    by_id = {n.id: n for n in nodes}
    roots = {n.id for n in nodes if n.parent_id is None}
    l1_nodes = [n for n in nodes if n.parent_id in roots]
    assert l1_nodes
    for chapter in l1_nodes:
        leaves = [n for n in nodes if n.parent_id == chapter.id]
        assert len(leaves) >= 8, f"{chapter.subject_code}/{chapter.name} has {len(leaves)} leaves"
        if chapter.meta_json and chapter.meta_json.get("tracks"):
            for leaf in leaves:
                assert leaf.meta_json == chapter.meta_json


def test_math2_excludes_gaoshu_leaves(db_session):
    seed_minimal_syllabus(db_session)
    leaves = leaf_nodes_for_placement(
        db_session,
        subject_code="math",
        exam_year=2027,
        math_track="math_2",
    )
    names = {n.name for n in leaves}
    assert "极限" not in names  # under 高数 / math_1
    assert names  # 线代/概率 leaves remain
