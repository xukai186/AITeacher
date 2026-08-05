from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    QuestionBankItem,
    SelfTestPaper,
    SelfTestQuestion,
    SelfTestSubmission,
)


@dataclass
class AssembledQuestion:
    bank_item_id: uuid.UUID | None
    selection_source: str
    knowledge_node_id: uuid.UUID | None
    q_type: str
    stem: str
    choices_json: list | None
    answer_key: str | None
    points: int
    seq: int


class SelfTestAssembler:
    def select_from_bank(
        self,
        db: Session,
        *,
        org_id: uuid.UUID,
        student_user_id: uuid.UUID,
        subject_code: str,
        count: int,
        exclude_bank_ids: set[uuid.UUID] | None = None,
    ) -> list[AssembledQuestion]:
        if count <= 0:
            return []

        submitted_ids = set(
            db.execute(
                select(SelfTestQuestion.bank_item_id)
                .join(SelfTestPaper, SelfTestPaper.id == SelfTestQuestion.paper_id)
                .join(
                    SelfTestSubmission,
                    SelfTestSubmission.paper_id == SelfTestPaper.id,
                )
                .where(
                    SelfTestSubmission.student_user_id == student_user_id,
                    SelfTestSubmission.status == "submitted",
                    SelfTestQuestion.bank_item_id.is_not(None),
                )
            )
            .scalars()
            .all()
        )
        excluded_ids = submitted_ids | set(exclude_bank_ids or ())
        selected: list[AssembledQuestion] = []

        for scope, source in (("org", "bank_org"), ("global", "bank_global")):
            remaining = count - len(selected)
            if remaining <= 0:
                break

            conditions = [
                QuestionBankItem.scope == scope,
                QuestionBankItem.subject_code == subject_code,
                QuestionBankItem.status == "active",
            ]
            if scope == "org":
                conditions.append(QuestionBankItem.org_id == org_id)

            statement = (
                select(QuestionBankItem)
                .where(*conditions)
                .order_by(
                    QuestionBankItem.created_at.asc(),
                    QuestionBankItem.id.asc(),
                )
                .limit(remaining)
            )
            if excluded_ids:
                statement = statement.where(
                    QuestionBankItem.id.not_in(excluded_ids)
                )

            for item in db.execute(statement).scalars():
                selected.append(
                    AssembledQuestion(
                        bank_item_id=item.id,
                        selection_source=source,
                        knowledge_node_id=item.knowledge_node_id,
                        q_type=item.q_type,
                        stem=item.stem,
                        choices_json=item.choices_json,
                        answer_key=item.answer_key,
                        points=1,
                        seq=len(selected) + 1,
                    )
                )

        return selected
