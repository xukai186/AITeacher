from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ModelPolicy, SyllabusNode
from app.services.report import ReportQuery, ReportService
from app.services.model_gateway import ModelGateway, ModelGatewayRequest

CHOICE_KEYS = ("A", "B", "C", "D")
DEFAULT_QUESTION_COUNT = 10


@dataclass(frozen=True)
class GeneratedQuestion:
    seq: int
    knowledge_node_id: uuid.UUID | None
    q_type: str
    stem: str
    choices_json: list[dict]
    answer_key: str
    points: int


class PaperGenService:
    def __init__(self, model_gateway: ModelGateway | None = None) -> None:
        self._gateway = model_gateway or ModelGateway()

    def generate_for_self_test(
        self,
        db: Session,
        *,
        org_id: uuid.UUID,
        student_user_id: uuid.UUID,
        subject_code: str,
        question_count: int = DEFAULT_QUESTION_COUNT,
    ) -> list[GeneratedQuestion]:
        policy = self._policy(db, org_id)
        overview = ReportService.overview(
            db,
            ReportQuery(student_user_id=student_user_id, subject_code=subject_code),
        )
        leaves = self._leaf_nodes(db, subject_code)
        if not leaves:
            raise ValueError("syllabus missing for subject")

        target_nodes = self._pick_target_nodes(
            db, overview.weak_nodes, leaves, question_count
        )

        if policy is None or policy.provider == "mock":
            return self._mock_questions(
                student_user_id, subject_code, target_nodes, question_count
            )

        try:
            raw = self._call_llm(
                policy.provider,
                policy.model,
                policy.params or {},
                subject_code=subject_code,
                target_nodes=target_nodes,
                question_count=question_count,
            )
            parsed = self._parse_llm_questions(
                raw, target_nodes=target_nodes, question_count=question_count
            )
            if parsed:
                return parsed
        except Exception:
            pass

        return self._deterministic_questions(
            student_user_id, subject_code, target_nodes, question_count
        )

    @staticmethod
    def _policy(db: Session, org_id: uuid.UUID) -> ModelPolicy | None:
        return db.execute(
            select(ModelPolicy).where(
                ModelPolicy.org_id == org_id,
                ModelPolicy.scene == "paper_gen",
            )
        ).scalar_one_or_none()

    @staticmethod
    def _leaf_nodes(db: Session, subject_code: str) -> list[SyllabusNode]:
        nodes = (
            db.execute(
                select(SyllabusNode)
                .where(SyllabusNode.subject_code == subject_code)
                .order_by(SyllabusNode.name)
            )
            .scalars()
            .all()
        )
        if not nodes:
            return []
        parent_ids = {n.parent_id for n in nodes if n.parent_id is not None}
        return [n for n in nodes if n.id not in parent_ids]

    @staticmethod
    def _pick_target_nodes(
        db: Session,
        weak_nodes: list,
        leaves: list[SyllabusNode],
        question_count: int,
    ) -> list[SyllabusNode]:
        by_id = {n.id: n for n in leaves}
        ordered: list[SyllabusNode] = []
        seen: set[uuid.UUID] = set()

        for weak in weak_nodes:
            node_id = weak.knowledge_node_id
            if node_id is None or node_id in seen:
                continue
            node = by_id.get(node_id)
            if node is None:
                node = db.get(SyllabusNode, node_id)
            if node is not None:
                ordered.append(node)
                seen.add(node.id)

        for node in leaves:
            if len(ordered) >= question_count:
                break
            if node.id not in seen:
                ordered.append(node)
                seen.add(node.id)

        if not ordered:
            ordered = list(leaves)
        return ordered

    def _call_llm(
        self,
        provider: str,
        model: str,
        params: dict,
        *,
        subject_code: str,
        target_nodes: list[SyllabusNode],
        question_count: int,
    ) -> str:
        nodes_payload = [
            {"id": str(n.id), "name": n.name} for n in target_nodes[:question_count]
        ]
        prompt = "\n".join(
            [
                "你是考研辅导命题老师。请为自测卷生成选择题。",
                f"科目代码：{subject_code}",
                f"需要题目数量：{question_count}",
                "优先覆盖以下知识点（薄弱点优先）：",
                json.dumps(nodes_payload, ensure_ascii=False),
                "",
                "只输出 STRICT JSON，不要 markdown：",
                json.dumps(
                    {
                        "questions": [
                            {
                                "seq": 1,
                                "knowledge_node_id": "<uuid>",
                                "q_type": "single_choice",
                                "stem": "<题干>",
                                "choices": [
                                    {"key": "A", "text": "<选项>"},
                                    {"key": "B", "text": "<选项>"},
                                    {"key": "C", "text": "<选项>"},
                                    {"key": "D", "text": "<选项>"},
                                ],
                                "answer_key": "A",
                                "points": 1,
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        resp = self._gateway.generate(
            ModelGatewayRequest(
                provider=provider,
                model=model,
                scene="paper_gen",
                prompt=prompt,
                params=params,
            )
        )
        return resp.text

    def _parse_llm_questions(
        self,
        raw: str,
        *,
        target_nodes: list[SyllabusNode],
        question_count: int,
    ) -> list[GeneratedQuestion]:
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()
        data = json.loads(text)
        items = data.get("questions") or []
        if not isinstance(items, list) or not items:
            return []

        allowed_ids = {n.id for n in target_nodes}
        out: list[GeneratedQuestion] = []
        for idx, item in enumerate(items[:question_count], start=1):
            node_raw = item.get("knowledge_node_id")
            node_id: uuid.UUID | None = None
            if node_raw:
                try:
                    node_id = uuid.UUID(str(node_raw))
                except ValueError:
                    node_id = None
            if node_id is not None and node_id not in allowed_ids:
                node_id = target_nodes[(idx - 1) % len(target_nodes)].id
            elif node_id is None:
                node_id = target_nodes[(idx - 1) % len(target_nodes)].id

            choices = item.get("choices") or []
            if not choices:
                continue
            answer_key = str(item.get("answer_key") or "A").strip().upper()
            if answer_key not in CHOICE_KEYS:
                answer_key = "A"

            out.append(
                GeneratedQuestion(
                    seq=int(item.get("seq") or idx),
                    knowledge_node_id=node_id,
                    q_type=str(item.get("q_type") or "single_choice"),
                    stem=str(item.get("stem") or f"第{idx}题"),
                    choices_json=[
                        {"key": str(c.get("key")), "text": str(c.get("text") or "")}
                        for c in choices
                        if c.get("key")
                    ],
                    answer_key=answer_key,
                    points=max(1, int(item.get("points") or 1)),
                )
            )
        return out

    @staticmethod
    def _answer_key(student_user_id: uuid.UUID, subject_code: str, seq: int) -> str:
        digest = hashlib.sha256(f"{student_user_id}:{subject_code}:{seq}".encode()).hexdigest()
        return CHOICE_KEYS[int(digest[:8], 16) % len(CHOICE_KEYS)]

    def _mock_questions(
        self,
        student_user_id: uuid.UUID,
        subject_code: str,
        target_nodes: list[SyllabusNode],
        question_count: int,
    ) -> list[GeneratedQuestion]:
        out: list[GeneratedQuestion] = []
        for seq in range(1, question_count + 1):
            node = target_nodes[(seq - 1) % len(target_nodes)]
            key = self._answer_key(student_user_id, subject_code, seq)
            choices = [{"key": k, "text": f"{node.name}相关表述 {k}"} for k in CHOICE_KEYS]
            out.append(
                GeneratedQuestion(
                    seq=seq,
                    knowledge_node_id=node.id,
                    q_type="single_choice",
                    stem=f"【薄弱巩固·{node.name}】请选择最符合考纲要求的选项（第{seq}题）",
                    choices_json=choices,
                    answer_key=key,
                    points=1,
                )
            )
        return out

    def _deterministic_questions(
        self,
        student_user_id: uuid.UUID,
        subject_code: str,
        target_nodes: list[SyllabusNode],
        question_count: int,
    ) -> list[GeneratedQuestion]:
        out: list[GeneratedQuestion] = []
        for seq in range(1, question_count + 1):
            node = target_nodes[(seq - 1) % len(target_nodes)]
            key = self._answer_key(student_user_id, subject_code, seq)
            choices = [{"key": k, "text": f"{node.name} — 选项{k}"} for k in CHOICE_KEYS]
            out.append(
                GeneratedQuestion(
                    seq=seq,
                    knowledge_node_id=node.id,
                    q_type="single_choice",
                    stem=f"【{node.name}】请选择最符合要求的选项（第{seq}题）",
                    choices_json=choices,
                    answer_key=key,
                    points=1,
                )
            )
        return out
