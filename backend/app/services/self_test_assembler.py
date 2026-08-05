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
    SyllabusNode,
    User,
    UserRole,
)
from app.services.master_plan_activation import MasterPlanActivationService
from app.services.paper_gen import PaperGenService, ProgressCallback
from app.services.question_bank import QuestionBankService
from app.services.report import ReportQuery, ReportService


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
    def _weak_node_ids(
        self,
        db: Session,
        *,
        student_user_id: uuid.UUID,
        subject_code: str,
    ) -> set[uuid.UUID]:
        try:
            overview = ReportService.overview(
                db,
                ReportQuery(
                    student_user_id=student_user_id,
                    subject_code=subject_code,
                ),
            )
        except Exception:
            return set()

        return {
            weak_node.knowledge_node_id
            for weak_node in overview.weak_nodes or []
            if weak_node.knowledge_node_id is not None
        }

    def _weekly_focus_node_ids(
        self,
        db: Session,
        *,
        student_user_id: uuid.UUID,
        subject_code: str,
    ) -> set[uuid.UUID]:
        try:
            state = MasterPlanActivationService().get_state(
                db,
                student_user_id=student_user_id,
            )
            active_version = state.get("active_version")
        except Exception:
            return set()

        if active_version is None:
            return set()

        node_ids: set[uuid.UUID] = set()
        for goal in active_version.weekly_goals_json or []:
            if not isinstance(goal, dict):
                continue
            if goal.get("kind") != "focus":
                continue
            if goal.get("subject_code") != subject_code:
                continue
            for raw_node_id in goal.get("syllabus_node_ids") or []:
                try:
                    node_ids.add(uuid.UUID(str(raw_node_id)))
                except (TypeError, ValueError):
                    continue
        return node_ids

    def assemble(
        self,
        db: Session,
        *,
        org_id: uuid.UUID,
        student_user_id: uuid.UUID,
        subject_code: str,
        question_count: int,
        provider: str | None,
        model: str | None,
        params: dict | None,
        target_nodes: list[SyllabusNode],
        english_track: str | None = None,
        math_track: str | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> list[AssembledQuestion]:
        assembled = self.select_from_bank(
            db,
            org_id=org_id,
            student_user_id=student_user_id,
            subject_code=subject_code,
            count=question_count,
        )
        gap = question_count - len(assembled)
        if gap <= 0:
            return assembled

        # Bank selection opens a read transaction; release it before the long LLM call.
        db.commit()
        generated = PaperGenService().generate_prepared_self_test(
            provider=provider,
            model=model,
            params=params,
            target_nodes=target_nodes,
            student_user_id=student_user_id,
            subject_code=subject_code,
            question_count=gap,
            english_track=english_track,
            math_track=math_track,
            on_progress=on_progress,
        )
        bank_service = QuestionBankService()
        creator = db.execute(
            select(User)
            .where(
                User.org_id == org_id,
                User.role.in_((UserRole.org_admin, UserRole.org_staff)),
            )
            .order_by(User.created_at.asc(), User.id.asc())
        ).scalars().first()
        if creator is None:
            student = db.get(User, student_user_id)
            if student is not None and student.org_id == org_id:
                creator = student
            else:
                creator = db.execute(
                    select(User)
                    .where(User.org_id == org_id)
                    .order_by(User.created_at.asc(), User.id.asc())
                ).scalars().first()
        if creator is None:
            raise ValueError("organization has no user for AI question ingest")

        for question in generated[:gap]:
            bank_item = bank_service.find_exact_duplicate(
                db,
                scope="org",
                org_id=org_id,
                q_type=question.q_type,
                stem=question.stem,
            )
            if bank_item is None or bank_item.status not in (
                "active",
                "pending_review",
            ):
                bank_item = bank_service.create(
                    db,
                    actor=creator,
                    scope="org",
                    org_id=org_id,
                    subject_code=subject_code,
                    knowledge_node_id=question.knowledge_node_id,
                    q_type=question.q_type,
                    stem=question.stem,
                    choices_json=question.choices_json,
                    answer_key=question.answer_key,
                    analysis_text=None,
                    difficulty=None,
                    source_type="ai_generated",
                    allow_inactive_duplicate=True,
                    allow_machine_actor=True,
                )
            assembled.append(
                AssembledQuestion(
                    bank_item_id=bank_item.id,
                    selection_source="ai_fallback",
                    knowledge_node_id=question.knowledge_node_id,
                    q_type=question.q_type,
                    stem=question.stem,
                    choices_json=question.choices_json,
                    answer_key=question.answer_key,
                    points=question.points,
                    seq=0,
                )
            )

        for seq, question in enumerate(assembled, start=1):
            question.seq = seq
        return assembled

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
