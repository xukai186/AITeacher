from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SyllabusNode


def resolve_syllabus_nodes(db: Session, node_ids: list[str]) -> list[dict]:
    if not node_ids:
        return []
    uuids: list[uuid.UUID] = []
    for raw in node_ids:
        try:
            uuids.append(uuid.UUID(str(raw)))
        except ValueError:
            continue
    if not uuids:
        return []
    nodes = list(
        db.execute(select(SyllabusNode).where(SyllabusNode.id.in_(uuids))).scalars().all()
    )
    by_id = {n.id: n for n in nodes}
    parent_ids = {n.parent_id for n in nodes if n.parent_id}
    parents = {}
    if parent_ids:
        parents = {
            p.id: p
            for p in db.execute(select(SyllabusNode).where(SyllabusNode.id.in_(parent_ids))).scalars()
        }
    out: list[dict] = []
    for raw in node_ids:
        try:
            uid = uuid.UUID(str(raw))
        except ValueError:
            continue
        node = by_id.get(uid)
        if node is None:
            continue
        parent = parents.get(node.parent_id) if node.parent_id else None
        out.append(
            {
                "id": str(node.id),
                "name": node.name,
                "parent_name": parent.name if parent else None,
            }
        )
    return out


def enrich_months_json(db: Session, months_json: dict | None) -> dict:
    if not months_json:
        return {"months": []}
    months = months_json.get("months") or []
    enriched_months = []
    for item in months:
        if not isinstance(item, dict):
            continue
        subjects = item.get("subjects") or {}
        new_subjects = {}
        if isinstance(subjects, dict):
            for code, block in subjects.items():
                if not isinstance(block, dict):
                    continue
                block_out = dict(block)
                ids = block.get("syllabus_node_ids") or []
                if ids:
                    block_out["syllabus_nodes_resolved"] = resolve_syllabus_nodes(db, list(ids))
                else:
                    names = block.get("syllabus_nodes") or []
                    block_out["syllabus_nodes_resolved"] = [
                        {"id": None, "name": str(n), "parent_name": None} for n in names if n
                    ]
                new_subjects[code] = block_out
        enriched_months.append({**item, "subjects": new_subjects})
    return {**months_json, "months": enriched_months}


def validate_months_leaf_ids(db: Session, months_json: dict | None) -> list[str]:
    """Return list of invalid id strings; empty if OK or legacy name-only."""
    if not months_json:
        return []
    has_ids = False
    invalid: list[str] = []
    seen: set[str] = set()
    all_ids: list[str] = []
    for item in months_json.get("months") or []:
        if not isinstance(item, dict):
            continue
        for block in (item.get("subjects") or {}).values():
            if not isinstance(block, dict):
                continue
            ids = block.get("syllabus_node_ids") or []
            if ids:
                has_ids = True
            for raw in ids:
                s = str(raw)
                if s in seen:
                    invalid.append(s)
                seen.add(s)
                all_ids.append(s)
    if not has_ids:
        return []
    resolved = resolve_syllabus_nodes(db, all_ids)
    ok = {r["id"] for r in resolved}
    for s in all_ids:
        if s not in ok:
            invalid.append(s)
    return invalid
