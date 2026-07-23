from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import WrongBookItem
from app.services.wrong_book import WrongBookService


def _item_payload(item: WrongBookItem, *, list_index: int) -> dict[str, Any]:
    snap = item.question_snapshot_json or {}
    answer = item.answer_snapshot_json or {}
    correct = item.correct_snapshot_json or {}
    return {
        "list_index": list_index,
        "item_id": str(item.id),
        "subject_code": item.subject_code,
        "source_type": item.source_type,
        "status": item.status,
        "stem": snap.get("stem"),
        "q_type": snap.get("q_type"),
        "choices": snap.get("choices") or [],
        "source_question_seq": snap.get("seq"),
        "source_question_id": snap.get("id"),
        "student_answer": answer.get("content"),
        "correct_answer": correct.get("answer_key"),
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def list_wrong_book_for_chat(
    db: Session,
    *,
    student_user_id: uuid.UUID,
    subject_code: str,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """List wrong-book items in the same order as the student Wrong Book page.

    ``list_index`` is 1-based across the filtered list (offset-aware), matching
    the on-page 「错题 N」 labels when the UI uses the same filters.
    Default status filter is None → active + mastered (same as the page).
    """
    limit = max(1, min(int(limit), 50))
    offset = max(0, int(offset))
    items = WrongBookService.list_items(
        db,
        student_user_id=student_user_id,
        subject_code=subject_code,
        status=status,
        limit=limit,
        offset=offset,
    )
    return {
        "subject_code": subject_code,
        "status_filter": status or "active+mastered",
        "offset": offset,
        "limit": limit,
        "count": len(items),
        "items": [
            _item_payload(item, list_index=offset + i + 1) for i, item in enumerate(items)
        ],
        "index_note": (
            "list_index 与学生端错题本列表「错题 N」一致（同科目、默认含待掌握+已掌握、创建时间倒序）。"
            "讲解错题本请用 explain_wrong_book_item，不要用试卷题号 explain_question。"
        ),
    }


def explain_wrong_book_item(
    db: Session,
    *,
    student_user_id: uuid.UUID,
    subject_code: str,
    list_index: int | None = None,
    item_id: uuid.UUID | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    if item_id is not None:
        item = db.get(WrongBookItem, item_id)
        if item is None or item.student_user_id != student_user_id:
            return {"error": "wrong book item not found"}
        if item.subject_code != subject_code:
            return {"error": "wrong book item subject mismatch"}
        # Resolve list_index in the filtered list for consistent labeling.
        all_items = WrongBookService.list_items(
            db,
            student_user_id=student_user_id,
            subject_code=subject_code,
            status=status,
            limit=200,
            offset=0,
        )
        list_index_resolved = next(
            (i + 1 for i, it in enumerate(all_items) if it.id == item.id),
            None,
        )
        payload = _item_payload(item, list_index=list_index_resolved or 0)
        payload["explanation_hint"] = _explanation_hint(item)
        return payload

    if list_index is None:
        return {"error": "list_index or item_id is required"}
    if list_index < 1:
        return {"error": "list_index must be >= 1"}

    # Fetch enough of the ordered list to resolve the index.
    page_size = 50
    page_offset = ((list_index - 1) // page_size) * page_size
    items = WrongBookService.list_items(
        db,
        student_user_id=student_user_id,
        subject_code=subject_code,
        status=status,
        limit=page_size,
        offset=page_offset,
    )
    pos = (list_index - 1) - page_offset
    if pos < 0 or pos >= len(items):
        return {"error": f"wrong book list_index {list_index} not found"}
    item = items[pos]
    payload = _item_payload(item, list_index=list_index)
    payload["explanation_hint"] = _explanation_hint(item)
    return payload


def _explanation_hint(item: WrongBookItem) -> str:
    snap = item.question_snapshot_json or {}
    correct = (item.correct_snapshot_json or {}).get("answer_key")
    student = (item.answer_snapshot_json or {}).get("content")
    source_seq = snap.get("seq")
    bits = [
        f"这是错题本条目（来源 {item.source_type}",
    ]
    if source_seq is not None:
        bits.append(f"，原卷第 {source_seq} 题")
    bits.append("）。")
    if correct is not None:
        bits.append(f"参考答案：{correct}。")
    if student is not None:
        bits.append(f"学生当时作答：{student}。")
    bits.append("请结合题干与干扰项讲解本题，勿与试卷其他题号混淆。")
    return "".join(bits)
