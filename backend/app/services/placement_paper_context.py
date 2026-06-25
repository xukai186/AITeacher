from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import PastExamPaperTemplate, PastExamQuestion, StudentProfile, SyllabusNode
from app.services.exam_profile import ExamProfileService

DEFAULT_EXAM_YEAR = 2027
PAST_EXAM_SAMPLE_LIMIT = 5
logger = logging.getLogger(__name__)
DEFAULT_PLACEMENT_SECTIONS = [
    {
        "section_name": "综合",
        "q_type": "single_choice",
        "count": 10,
        "knowledge_area": None,
        "points": 1,
    },
]


@dataclass(frozen=True)
class PlacementSlot:
    seq: int
    section_name: str
    q_type: str
    knowledge_node: SyllabusNode
    section_index: int
    points: int


def materialize_placement_slots(slots: list[PlacementSlot]) -> list[PlacementSlot]:
    """Copy slots with detached SyllabusNode rows safe to use after Session close."""
    out: list[PlacementSlot] = []
    for slot in slots:
        node = slot.knowledge_node
        detached_node = SyllabusNode(
            id=node.id,
            subject_code=node.subject_code,
            name=node.name,
            parent_id=node.parent_id,
        )
        out.append(
            PlacementSlot(
                seq=slot.seq,
                section_name=slot.section_name,
                q_type=slot.q_type,
                knowledge_node=detached_node,
                section_index=slot.section_index,
                points=slot.points,
            )
        )
    return out


def materialize_syllabus_nodes(nodes: list[SyllabusNode]) -> list[SyllabusNode]:
    return [
        SyllabusNode(
            id=node.id,
            subject_code=node.subject_code,
            name=node.name,
            parent_id=node.parent_id,
        )
        for node in nodes
    ]


@dataclass(frozen=True)
class PlacementGenContext:
    exam_year: int
    syllabus_outline: list[dict]
    past_exam_samples: list[dict]
    paper_title: str
    reference_year: int | None
    paper_sections: list[dict]
    english_track: str | None = None
    math_track: str | None = None


def resolve_student_exam_year(db: Session, student_user_id: uuid.UUID) -> int:
    profile = db.get(StudentProfile, student_user_id)
    if profile is not None:
        return profile.exam_year
    return DEFAULT_EXAM_YEAR


def resolve_placement_tracks(
    db: Session,
    *,
    student_user_id: uuid.UUID,
    english_track: str | None = None,
    math_track: str | None = None,
) -> tuple[str | None, str | None]:
    effective = ExamProfileService().get_effective(db, student_user_id)
    if effective is None:
        return english_track, math_track
    resolved_english = english_track if english_track is not None else effective.english_track
    resolved_math = math_track if math_track is not None else effective.math_track
    return resolved_english, resolved_math


def _node_matches_track(
    node: SyllabusNode,
    *,
    subject_code: str,
    english_track: str | None,
    math_track: str | None,
) -> bool:
    meta = node.meta_json or {}
    tracks = meta.get("tracks")
    if not tracks:
        return True
    if subject_code == "math":
        student_track = math_track
    elif subject_code == "english":
        student_track = english_track
    else:
        return True
    if not student_track:
        return True
    if student_track == "none":
        return False
    return student_track in tracks


def filter_nodes_for_track(
    nodes: list[SyllabusNode],
    *,
    subject_code: str,
    english_track: str | None = None,
    math_track: str | None = None,
) -> list[SyllabusNode]:
    return [
        node
        for node in nodes
        if _node_matches_track(
            node,
            subject_code=subject_code,
            english_track=english_track,
            math_track=math_track,
        )
    ]


def load_paper_template(
    db: Session,
    *,
    subject_code: str,
    syllabus_exam_year: int,
    english_track: str | None = None,
    math_track: str | None = None,
) -> PastExamPaperTemplate | None:
    stmt = (
        select(PastExamPaperTemplate)
        .where(
            PastExamPaperTemplate.subject_code == subject_code,
            PastExamPaperTemplate.syllabus_exam_year == syllabus_exam_year,
        )
        .order_by(PastExamPaperTemplate.reference_year.desc())
        .limit(1)
    )

    has_track_filter = False
    if subject_code == "english" and english_track:
        stmt = stmt.where(PastExamPaperTemplate.english_track == english_track)
        has_track_filter = True
    elif subject_code == "math" and math_track:
        stmt = stmt.where(PastExamPaperTemplate.math_track == math_track)
        has_track_filter = True
    elif subject_code == "politics":
        stmt = stmt.where(
            PastExamPaperTemplate.english_track.is_(None),
            PastExamPaperTemplate.math_track.is_(None),
        )

    template = db.execute(stmt).scalar_one_or_none()
    if template is not None:
        return template

    if not has_track_filter:
        return None

    logger.warning(
        "No placement template found for subject=%s year=%s english_track=%s math_track=%s; "
        "falling back to subject-only match",
        subject_code,
        syllabus_exam_year,
        english_track,
        math_track,
    )
    return db.execute(
        select(PastExamPaperTemplate)
        .where(
            PastExamPaperTemplate.subject_code == subject_code,
            PastExamPaperTemplate.syllabus_exam_year == syllabus_exam_year,
        )
        .order_by(PastExamPaperTemplate.reference_year.desc())
        .limit(1)
    ).scalar_one_or_none()


def resolve_placement_paper_title(
    db: Session,
    *,
    subject_code: str,
    student_user_id: uuid.UUID,
    english_track: str | None = None,
    math_track: str | None = None,
) -> str:
    exam_year = resolve_student_exam_year(db, student_user_id)
    template = load_paper_template(
        db,
        subject_code=subject_code,
        syllabus_exam_year=exam_year,
        english_track=english_track,
        math_track=math_track,
    )
    if template is not None:
        return template.title
    return f"{subject_code} 模拟摸底卷"


def resolve_placement_question_count(
    db: Session,
    *,
    subject_code: str,
    student_user_id: uuid.UUID,
    english_track: str | None = None,
    math_track: str | None = None,
) -> int:
    ctx = build_placement_context(
        db,
        student_user_id=student_user_id,
        subject_code=subject_code,
        english_track=english_track,
        math_track=math_track,
    )
    return sum(int(section.get("count") or 0) for section in ctx.paper_sections)


def syllabus_nodes_for_year(
    db: Session, *, subject_code: str, exam_year: int
) -> list[SyllabusNode]:
    return list(
        db.execute(
            select(SyllabusNode)
            .where(
                SyllabusNode.subject_code == subject_code,
                or_(SyllabusNode.exam_year.is_(None), SyllabusNode.exam_year == exam_year),
            )
            .order_by(SyllabusNode.name)
        )
        .scalars()
        .all()
    )


def leaf_nodes_for_placement(
    db: Session,
    *,
    subject_code: str,
    exam_year: int,
    english_track: str | None = None,
    math_track: str | None = None,
) -> list[SyllabusNode]:
    nodes = syllabus_nodes_for_year(db, subject_code=subject_code, exam_year=exam_year)
    nodes = filter_nodes_for_track(
        nodes,
        subject_code=subject_code,
        english_track=english_track,
        math_track=math_track,
    )
    if not nodes:
        return []
    parent_ids = {n.parent_id for n in nodes if n.parent_id is not None}
    return [n for n in nodes if n.id not in parent_ids]


def _build_syllabus_outline(nodes: list[SyllabusNode]) -> list[dict]:
    by_id = {n.id: n for n in nodes}
    outline: list[dict] = []
    for node in nodes:
        parent = by_id.get(node.parent_id) if node.parent_id else None
        outline.append(
            {
                "id": str(node.id),
                "name": node.name,
                "parent_name": parent.name if parent else None,
                "weight": node.weight,
            }
        )
    return outline


def load_past_exam_samples(
    db: Session,
    *,
    subject_code: str,
    syllabus_exam_year: int,
    limit: int = PAST_EXAM_SAMPLE_LIMIT,
) -> list[PastExamQuestion]:
    return list(
        db.execute(
            select(PastExamQuestion)
            .where(
                PastExamQuestion.subject_code == subject_code,
                PastExamQuestion.syllabus_exam_year == syllabus_exam_year,
            )
            .order_by(PastExamQuestion.source_year.desc(), PastExamQuestion.created_at.asc())
            .limit(limit)
        )
        .scalars()
        .all()
    )


def past_exam_sample_payload(
    db: Session, samples: list[PastExamQuestion]
) -> list[dict]:
    out: list[dict] = []
    for sample in samples:
        node_name: str | None = None
        if sample.knowledge_node_id is not None:
            node = db.get(SyllabusNode, sample.knowledge_node_id)
            if node is not None:
                node_name = node.name
        out.append(
            {
                "source_year": sample.source_year,
                "q_type": sample.q_type,
                "knowledge_node_id": str(sample.knowledge_node_id) if sample.knowledge_node_id else None,
                "knowledge_node_name": node_name,
                "stem": sample.stem,
                "choices": sample.choices_json or [],
                "answer_key": sample.answer_key,
            }
        )
    return out


def _resolve_node_for_area(
    leaves: list[SyllabusNode],
    knowledge_area: str | None,
    *,
    fallback_index: int,
    weak_node_ids: set[uuid.UUID],
) -> SyllabusNode:
    by_name = {n.name: n for n in leaves}
    if knowledge_area and knowledge_area in by_name:
        return by_name[knowledge_area]
    for node in leaves:
        if node.id in weak_node_ids:
            return node
    return leaves[fallback_index % len(leaves)]


def build_placement_slots(
    db: Session,
    context: PlacementGenContext,
    leaves: list[SyllabusNode],
    weak_nodes: list,
) -> list[PlacementSlot]:
    if not leaves:
        return []

    weak_ids = {
        w.knowledge_node_id for w in weak_nodes if getattr(w, "knowledge_node_id", None) is not None
    }
    slots: list[PlacementSlot] = []
    seq = 1
    for section in context.paper_sections:
        section_name = str(section.get("section_name") or "综合")
        q_type = str(section.get("q_type") or "single_choice")
        count = int(section.get("count") or 0)
        knowledge_area = section.get("knowledge_area")
        points = int(section.get("points") or 1)
        for section_index in range(1, count + 1):
            node = _resolve_node_for_area(
                leaves,
                knowledge_area,
                fallback_index=seq - 1,
                weak_node_ids=weak_ids,
            )
            slots.append(
                PlacementSlot(
                    seq=seq,
                    section_name=section_name,
                    q_type=q_type,
                    knowledge_node=node,
                    section_index=section_index,
                    points=points,
                )
            )
            seq += 1
    return slots


def placement_questions_match_template(
    db: Session,
    *,
    student_user_id: uuid.UUID,
    subject_code: str,
    questions: list,
) -> bool:
    ctx = build_placement_context(
        db, student_user_id=student_user_id, subject_code=subject_code
    )
    leaves = leaf_nodes_for_placement(
        db,
        subject_code=subject_code,
        exam_year=ctx.exam_year,
        english_track=ctx.english_track,
        math_track=ctx.math_track,
    )
    if not leaves:
        return False
    slots = build_placement_slots(db, ctx, leaves, [])
    ordered = sorted(questions, key=lambda q: q.seq)
    if len(ordered) != len(slots):
        return False
    for question, slot in zip(ordered, slots):
        if question.q_type != slot.q_type or question.points != slot.points:
            return False
    return True


def build_placement_context(
    db: Session,
    *,
    student_user_id: uuid.UUID,
    subject_code: str,
    english_track: str | None = None,
    math_track: str | None = None,
) -> PlacementGenContext:
    exam_year = resolve_student_exam_year(db, student_user_id)
    english_track, math_track = resolve_placement_tracks(
        db,
        student_user_id=student_user_id,
        english_track=english_track,
        math_track=math_track,
    )
    nodes = syllabus_nodes_for_year(db, subject_code=subject_code, exam_year=exam_year)
    nodes = filter_nodes_for_track(
        nodes,
        subject_code=subject_code,
        english_track=english_track,
        math_track=math_track,
    )
    samples = load_past_exam_samples(
        db, subject_code=subject_code, syllabus_exam_year=exam_year
    )
    template = load_paper_template(
        db,
        subject_code=subject_code,
        syllabus_exam_year=exam_year,
        english_track=english_track,
        math_track=math_track,
    )
    if template is not None:
        paper_title = template.title
        reference_year = template.reference_year
        paper_sections = list(template.sections_json or [])
    else:
        paper_title = f"{subject_code} 模拟摸底卷"
        reference_year = None
        paper_sections = list(DEFAULT_PLACEMENT_SECTIONS)

    return PlacementGenContext(
        exam_year=exam_year,
        syllabus_outline=_build_syllabus_outline(nodes),
        past_exam_samples=past_exam_sample_payload(db, samples),
        paper_title=paper_title,
        reference_year=reference_year,
        paper_sections=paper_sections,
        english_track=english_track,
        math_track=math_track,
    )


def reference_year_for_node(
    context: PlacementGenContext,
    node_id: uuid.UUID,
    *,
    fallback_seq: int,
) -> int | None:
    if context.reference_year is not None:
        return context.reference_year
    node_key = str(node_id)
    for sample in context.past_exam_samples:
        if sample.get("knowledge_node_id") == node_key:
            return int(sample["source_year"])
    if context.past_exam_samples:
        idx = (fallback_seq - 1) % len(context.past_exam_samples)
        return int(context.past_exam_samples[idx]["source_year"])
    return None
