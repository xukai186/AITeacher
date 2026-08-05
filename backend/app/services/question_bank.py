from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.models import QuestionBankItem, User, UserRole
from app.schemas.question_bank import QuestionBankCreate


class QuestionBankService:
    _SOURCE_STATUSES = {
        "admin_manual": "active",
        "staff_manual": "active",
        "ocr_import": "pending_review",
        "ai_generated": "pending_review",
    }

    def create(
        self,
        db: Session,
        *,
        actor: User,
        payload: QuestionBankCreate | None = None,
        scope: str | None = None,
        org_id: uuid.UUID | None = None,
        subject_code: str | None = None,
        knowledge_node_id: uuid.UUID | None = None,
        q_type: str | None = None,
        stem: str | None = None,
        choices_json: list[dict] | None = None,
        answer_key: str | None = None,
        analysis_text: str | None = None,
        difficulty: int | None = None,
        source_type: str | None = None,
        source_image_asset_id: uuid.UUID | None = None,
        allow_inactive_duplicate: bool = False,
        allow_machine_actor: bool = False,
    ) -> QuestionBankItem:
        if payload is not None:
            if any(
                value is not None
                for value in (
                    scope,
                    org_id,
                    subject_code,
                    knowledge_node_id,
                    q_type,
                    stem,
                    choices_json,
                    answer_key,
                    analysis_text,
                    difficulty,
                    source_type,
                    source_image_asset_id,
                )
            ):
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "pass either payload or question fields, not both",
                )
            values = payload.model_dump()
            scope = values["scope"]
            org_id = values["org_id"]
            subject_code = values["subject_code"]
            knowledge_node_id = values["knowledge_node_id"]
            q_type = values["q_type"]
            stem = values["stem"]
            choices_json = values["choices_json"]
            answer_key = values["answer_key"]
            analysis_text = values["analysis_text"]
            difficulty = values["difficulty"]
            source_type = values["source_type"]
            source_image_asset_id = values["source_image_asset_id"]
        elif any(value is None for value in (scope, subject_code, q_type, stem, source_type)):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "missing required question bank fields",
            )

        assert scope is not None
        assert subject_code is not None
        assert q_type is not None
        assert stem is not None
        assert source_type is not None
        item_status = self._SOURCE_STATUSES.get(source_type)
        if item_status is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "unsupported question bank source type",
            )
        self._authorize_create(
            actor,
            scope=scope,
            org_id=org_id,
            allow_machine_actor=allow_machine_actor and source_type == "ai_generated",
        )

        normalized_stem = stem.strip()
        duplicate = self.find_exact_duplicate(
            db,
            scope=scope,
            org_id=org_id,
            q_type=q_type,
            stem=normalized_stem,
        )
        if duplicate is not None and not (
            allow_inactive_duplicate
            and duplicate.status not in ("active", "pending_review")
        ):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "exact question bank duplicate",
            )

        item = QuestionBankItem(
            scope=scope,
            org_id=org_id,
            subject_code=subject_code,
            knowledge_node_id=knowledge_node_id,
            q_type=q_type,
            stem=normalized_stem,
            choices_json=choices_json,
            answer_key=answer_key,
            analysis_text=analysis_text,
            difficulty=difficulty,
            source_type=source_type,
            status=item_status,
            created_by=actor.id,
            source_image_asset_id=source_image_asset_id,
        )
        db.add(item)
        db.flush()
        return item

    def list(
        self,
        db: Session,
        *,
        viewer: User,
        status: str | None = None,
        subject_code: str | None = None,
        pending_only: bool = False,
    ) -> list[QuestionBankItem]:
        self._require_staff(viewer)
        if viewer.role == UserRole.org_admin:
            visibility = or_(
                QuestionBankItem.org_id == viewer.org_id,
                QuestionBankItem.scope == "global",
            )
        else:
            visibility = QuestionBankItem.org_id == viewer.org_id

        stmt = select(QuestionBankItem).where(visibility)
        if pending_only:
            stmt = stmt.where(QuestionBankItem.status == "pending_review")
        elif status is not None:
            stmt = stmt.where(QuestionBankItem.status == status)
        if subject_code is not None:
            stmt = stmt.where(QuestionBankItem.subject_code == subject_code)

        stmt = stmt.order_by(
            QuestionBankItem.created_at.desc(),
            QuestionBankItem.id.desc(),
        )
        return list(db.execute(stmt).scalars().all())

    def approve(
        self,
        db: Session,
        *,
        actor: User,
        item_id: uuid.UUID,
    ) -> QuestionBankItem:
        item = self._get_mutable_item(db, actor=actor, item_id=item_id)
        self._require_status(item, "pending_review")
        item.status = "active"
        self._record_review(item, actor)
        db.flush()
        return item

    def reject(
        self,
        db: Session,
        *,
        actor: User,
        item_id: uuid.UUID,
    ) -> QuestionBankItem:
        item = self._get_mutable_item(db, actor=actor, item_id=item_id)
        self._require_status(item, "pending_review")
        item.status = "rejected"
        self._record_review(item, actor)
        db.flush()
        return item

    def disable(
        self,
        db: Session,
        *,
        actor: User,
        item_id: uuid.UUID,
    ) -> QuestionBankItem:
        item = self._get_mutable_item(db, actor=actor, item_id=item_id)
        self._require_status(item, "active")
        item.status = "disabled"
        db.flush()
        return item

    def find_exact_duplicate(
        self,
        db: Session,
        *,
        scope: str,
        org_id: uuid.UUID | None,
        q_type: str,
        stem: str,
    ) -> QuestionBankItem | None:
        normalized_stem = stem.strip()
        return db.execute(
            select(QuestionBankItem)
            .where(
                QuestionBankItem.scope == scope,
                QuestionBankItem.org_id == org_id,
                QuestionBankItem.q_type == q_type,
                func.btrim(QuestionBankItem.stem) == normalized_stem,
            )
            .order_by(
                case(
                    (QuestionBankItem.status == "active", 0),
                    (QuestionBankItem.status == "pending_review", 1),
                    else_=2,
                ),
                QuestionBankItem.created_at.desc(),
                QuestionBankItem.id.desc(),
            )
            .limit(1)
        ).scalars().first()

    @staticmethod
    def _require_staff(actor: User) -> None:
        if actor.role not in (UserRole.org_admin, UserRole.org_staff):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "question bank access requires staff",
            )

    def _authorize_create(
        self,
        actor: User,
        *,
        scope: str,
        org_id: uuid.UUID | None,
        allow_machine_actor: bool = False,
    ) -> None:
        if allow_machine_actor:
            if scope != "org" or org_id != actor.org_id:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    "machine-authored items must belong to the actor organization",
                )
            return
        self._require_staff(actor)
        if scope not in ("org", "global"):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "unsupported question bank scope",
            )
        if scope == "global":
            if actor.role != UserRole.org_admin:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    "staff cannot create global question bank items",
                )
            if org_id is not None:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "global question bank items cannot have an organization",
                )
        elif org_id != actor.org_id:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "cannot create question bank items for another organization",
            )

    def _get_mutable_item(
        self,
        db: Session,
        *,
        actor: User,
        item_id: uuid.UUID,
    ) -> QuestionBankItem:
        self._require_staff(actor)
        item = db.get(QuestionBankItem, item_id, with_for_update=True)
        if item is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "question bank item not found",
            )
        if item.scope == "global":
            if actor.role != UserRole.org_admin:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    "staff cannot mutate global question bank items",
                )
        elif item.org_id != actor.org_id:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "question bank item not found",
            )
        return item

    @staticmethod
    def _require_status(item: QuestionBankItem, expected: str) -> None:
        if item.status != expected:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"question bank item must be {expected}",
            )

    @staticmethod
    def _record_review(item: QuestionBankItem, actor: User) -> None:
        item.reviewed_by = actor.id
        item.reviewed_at = datetime.now(timezone.utc)
