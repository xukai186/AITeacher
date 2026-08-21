from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.permissions import require_roles
from app.database import get_db
from app.models import QuestionBankItem, SyllabusNode, User, UserRole
from app.schemas.question_bank import (
    KnowledgeNodeOptionOut,
    MediaAssetOut,
    QuestionBankCreate,
    QuestionBankCreateRequest,
    QuestionBankItemOut,
    QuestionBankUpdateRequest,
    QuestionEnrichmentOut,
    QuestionEnrichmentRequest,
    QuestionDraftOut,
    QuestionOCROut,
    QuestionOCRRawTextFallbackOut,
    QuestionOCRRequest,
    QuestionOCRResponse,
    QuestionOCRSegmentedOut,
    QuestionOCRSingleQuestionOut,
)
from app.services.media_assets import MediaAssetService, UploadTooLargeError
from app.services.question_bank import QuestionBankService, _UNSET
from app.services.question_enrichment import QuestionEnrichmentService
from app.services.question_ocr import QuestionOCRService
from app.services.roadmap_resolve import resolve_syllabus_nodes

router = APIRouter(prefix="/org/question-bank", tags=["org-question-bank"])
staff_or_admin = require_roles(UserRole.org_admin, UserRole.org_staff)


@router.post("/upload-image", response_model=MediaAssetOut, status_code=status.HTTP_201_CREATED)
def upload_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: User = Depends(staff_or_admin),
) -> MediaAssetOut:
    try:
        asset = MediaAssetService().store(
            db,
            org_id=actor.org_id,
            created_by=actor.id,
            content_type=file.content_type or "application/octet-stream",
            source=file.file,
        )
    except UploadTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)) from exc
    db.commit()
    db.refresh(asset)
    return MediaAssetOut(
        asset_id=asset.id,
        storage_key=f"{asset.org_id}/{asset.id}",
    )


@router.post("/ocr")
def extract_question(
    payload: QuestionOCRRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(staff_or_admin),
) -> QuestionOCRResponse | QuestionOCROut:
    svc = QuestionOCRService()
    try:
        if payload.mode == "single_image_multi_question":
            result = svc.extract_segmented(
                db, org_id=actor.org_id, asset_id=payload.asset_ids[0]
            )
            if result.kind == "raw_text_fallback":
                return QuestionOCRRawTextFallbackOut(raw_text=result.raw_text)
            return QuestionOCRSegmentedOut(
                questions=[
                    QuestionDraftOut(
                        q_type=q.q_type,
                        stem=q.stem,
                        choices=q.choices,
                        answer_key=q.answer_key,
                    )
                    for q in result.questions
                ]
            )
        if payload.mode == "multi_image_single_question":
            question = svc.extract_merged(
                db, org_id=actor.org_id, asset_ids=payload.asset_ids
            )
            return QuestionOCRSingleQuestionOut(
                question=QuestionDraftOut(
                    q_type=question.q_type,
                    stem=question.stem,
                    choices=question.choices,
                    answer_key=question.answer_key,
                )
            )
        question = svc.extract(
            db, org_id=actor.org_id, asset_id=payload.asset_ids[0]
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="OCR extraction failed") from exc
    return QuestionOCROut(
        q_type=question.q_type,
        stem=question.stem,
        choices=question.choices,
        answer_key=question.answer_key,
    )


def _node_label(resolved: dict | None) -> str | None:
    if resolved is None:
        return None
    parent_name = resolved.get("parent_name")
    name = resolved.get("name")
    if not name:
        return None
    if parent_name:
        return f"{parent_name} / {name}"
    return str(name)


def _item_out(
    item: QuestionBankItem,
    *,
    knowledge_node_name: str | None = None,
) -> QuestionBankItemOut:
    return QuestionBankItemOut(
        id=item.id,
        scope=item.scope,
        org_id=item.org_id,
        subject_code=item.subject_code,
        knowledge_node_id=item.knowledge_node_id,
        knowledge_node_name=knowledge_node_name,
        q_type=item.q_type,
        stem=item.stem,
        choices=item.choices_json,
        answer_key=item.answer_key,
        analysis_text=item.analysis_text,
        difficulty=item.difficulty,
        source_type=item.source_type,
        status=item.status,
        created_by=item.created_by,
        reviewed_by=item.reviewed_by,
        reviewed_at=item.reviewed_at,
        source_image_asset_id=item.source_image_asset_id,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _items_out(db: Session, items: list[QuestionBankItem]) -> list[QuestionBankItemOut]:
    node_ids = [str(item.knowledge_node_id) for item in items if item.knowledge_node_id]
    resolved = {
        row["id"]: row for row in resolve_syllabus_nodes(db, node_ids)
    }
    return [
        _item_out(
            item,
            knowledge_node_name=_node_label(
                resolved.get(str(item.knowledge_node_id)) if item.knowledge_node_id else None
            ),
        )
        for item in items
    ]


def _single_item_out(db: Session, item: QuestionBankItem) -> QuestionBankItemOut:
    return _items_out(db, [item])[0]


@router.post("/enrich", response_model=QuestionEnrichmentOut)
def enrich_question(
    payload: QuestionEnrichmentRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(staff_or_admin),
) -> QuestionEnrichmentOut:
    suggestion = QuestionEnrichmentService().suggest(
        db,
        org_id=actor.org_id,
        stem=payload.stem,
        q_type=payload.q_type,
        choices_json=payload.choices,
        answer_key=payload.answer_key,
    )
    return QuestionEnrichmentOut(
        subject_code=suggestion.subject_code,
        knowledge_node_id=suggestion.knowledge_node_id,
        knowledge_node_name=_node_label(
            resolve_syllabus_nodes(
                db,
                [str(suggestion.knowledge_node_id)],
            )[0]
            if suggestion.knowledge_node_id
            else None
        ),
        difficulty=suggestion.difficulty,
        analysis_text=suggestion.analysis_text,
        q_type=suggestion.q_type,
    )


@router.post("", response_model=QuestionBankItemOut, status_code=status.HTTP_201_CREATED)
def create_question(
    payload: QuestionBankCreateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(staff_or_admin),
) -> QuestionBankItemOut:
    item = QuestionBankService().create(
        db,
        actor=actor,
        payload=QuestionBankCreate(
            scope=payload.scope,
            org_id=actor.org_id if payload.scope == "org" else None,
            subject_code=payload.subject_code,
            knowledge_node_id=payload.knowledge_node_id,
            q_type=payload.q_type,
            stem=payload.stem,
            choices_json=payload.choices,
            answer_key=payload.answer_key,
            analysis_text=payload.analysis_text,
            difficulty=payload.difficulty,
            source_type=payload.source_type,
            source_image_asset_id=payload.source_image_asset_id,
        ),
    )
    db.commit()
    db.refresh(item)
    return _single_item_out(db, item)


@router.get("", response_model=list[QuestionBankItemOut])
def list_questions(
    status_filter: str | None = Query(default=None, alias="status"),
    subject_code: str | None = None,
    pending: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    actor: User = Depends(staff_or_admin),
) -> list[QuestionBankItemOut]:
    items = QuestionBankService().list(
        db,
        viewer=actor,
        status=status_filter,
        subject_code=subject_code,
        pending_only=pending,
        limit=limit,
        offset=offset,
    )
    return _items_out(db, items)


@router.get("/knowledge-nodes", response_model=list[KnowledgeNodeOptionOut])
def list_knowledge_nodes(
    subject_code: str,
    db: Session = Depends(get_db),
    actor: User = Depends(staff_or_admin),
) -> list[KnowledgeNodeOptionOut]:
    nodes = QuestionBankService().list_leaf_knowledge_nodes(db, subject_code=subject_code)
    parent_ids = {n.parent_id for n in nodes if n.parent_id}
    parents: dict = {}
    if parent_ids:
        parents = {
            p.id: p
            for p in db.execute(
                select(SyllabusNode).where(SyllabusNode.id.in_(parent_ids))
            ).scalars()
        }
    out: list[KnowledgeNodeOptionOut] = []
    for node in nodes:
        parent = parents.get(node.parent_id) if node.parent_id else None
        out.append(
            KnowledgeNodeOptionOut(
                id=node.id,
                name=node.name,
                parent_name=parent.name if parent else None,
            )
        )
    return out


@router.patch("/{item_id}", response_model=QuestionBankItemOut)
def update_question(
    item_id: uuid.UUID,
    payload: QuestionBankUpdateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(staff_or_admin),
) -> QuestionBankItemOut:
    data = payload.model_dump(exclude_unset=True)
    item = QuestionBankService().update(
        db,
        actor=actor,
        item_id=item_id,
        stem=data.get("stem"),
        q_type=data.get("q_type"),
        choices_json=data.get("choices"),
        answer_key=data.get("answer_key"),
        subject_code=data.get("subject_code"),
        knowledge_node_id=data["knowledge_node_id"] if "knowledge_node_id" in data else _UNSET,
        difficulty=data.get("difficulty"),
        analysis_text=data["analysis_text"] if "analysis_text" in data else _UNSET,
    )
    db.commit()
    db.refresh(item)
    return _single_item_out(db, item)


def _review(
    action: str,
    item_id: uuid.UUID,
    db: Session,
    actor: User,
) -> QuestionBankItemOut:
    service = QuestionBankService()
    item = getattr(service, action)(db, actor=actor, item_id=item_id)
    db.commit()
    db.refresh(item)
    return _single_item_out(db, item)


@router.post("/{item_id}/approve", response_model=QuestionBankItemOut)
def approve_question(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(staff_or_admin),
) -> QuestionBankItemOut:
    return _review("approve", item_id, db, actor)


@router.post("/{item_id}/reject", response_model=QuestionBankItemOut)
def reject_question(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(staff_or_admin),
) -> QuestionBankItemOut:
    return _review("reject", item_id, db, actor)


@router.post("/{item_id}/disable", response_model=QuestionBankItemOut)
def disable_question(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(staff_or_admin),
) -> QuestionBankItemOut:
    return _review("disable", item_id, db, actor)


@router.post("/{item_id}/delete", response_model=QuestionBankItemOut)
def delete_question(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(staff_or_admin),
) -> QuestionBankItemOut:
    return _review("delete", item_id, db, actor)
