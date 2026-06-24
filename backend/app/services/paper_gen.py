from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ModelPolicy, SyllabusNode
from app.services.placement_paper_context import (
    PlacementGenContext,
    PlacementSlot,
    build_placement_context,
    build_placement_slots,
    leaf_nodes_for_placement,
    reference_year_for_node,
)
from app.services.report import ReportQuery, ReportService
from app.services.model_gateway import ModelGateway, ModelGatewayRequest

CHOICE_KEYS = ("A", "B", "C", "D")
DEFAULT_QUESTION_COUNT = 10
LLM_BATCH_SIZE = 3
PAPER_GEN_TIMEOUT = httpx.Timeout(180.0, connect=15.0)
PaperPurpose = Literal["self_test", "placement"]
ProgressCallback = Callable[[int, int, str], None]
MOCK_PLACEMENT_STEM_PREFIX = "【模拟摸底·"


def is_mock_placement_stem(stem: str) -> bool:
    return stem.startswith(MOCK_PLACEMENT_STEM_PREFIX)


@dataclass(frozen=True)
class GeneratedQuestion:
    seq: int
    knowledge_node_id: uuid.UUID | None
    q_type: str
    stem: str
    choices_json: list[dict] | None
    answer_key: str
    points: int
    rubric_json: dict | None = None


class PaperGenService:
    def __init__(self, model_gateway: ModelGateway | None = None) -> None:
        self._gateway = model_gateway or ModelGateway(
            http_client=httpx.Client(timeout=PAPER_GEN_TIMEOUT)
        )

    def generate_for_self_test(
        self,
        db: Session,
        *,
        org_id: uuid.UUID,
        student_user_id: uuid.UUID,
        subject_code: str,
        question_count: int = DEFAULT_QUESTION_COUNT,
        on_progress: ProgressCallback | None = None,
    ) -> list[GeneratedQuestion]:
        return self.generate(
            db,
            org_id=org_id,
            student_user_id=student_user_id,
            subject_code=subject_code,
            question_count=question_count,
            purpose="self_test",
            on_progress=on_progress,
        )

    def generate_for_placement(
        self,
        db: Session,
        *,
        org_id: uuid.UUID,
        student_user_id: uuid.UUID,
        subject_code: str,
        question_count: int | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> list[GeneratedQuestion]:
        return self.generate(
            db,
            org_id=org_id,
            student_user_id=student_user_id,
            subject_code=subject_code,
            question_count=question_count,
            purpose="placement",
            on_progress=on_progress,
        )

    def generate(
        self,
        db: Session,
        *,
        org_id: uuid.UUID,
        student_user_id: uuid.UUID,
        subject_code: str,
        question_count: int | None = DEFAULT_QUESTION_COUNT,
        purpose: PaperPurpose = "self_test",
        on_progress: ProgressCallback | None = None,
    ) -> list[GeneratedQuestion]:
        policy = self._policy(db, org_id)
        overview = ReportService.overview(
            db,
            ReportQuery(student_user_id=student_user_id, subject_code=subject_code),
        )

        placement_context: PlacementGenContext | None = None
        placement_slots: list[PlacementSlot] | None = None
        if purpose == "placement":
            placement_context = build_placement_context(
                db, student_user_id=student_user_id, subject_code=subject_code
            )
            leaves = leaf_nodes_for_placement(
                db,
                subject_code=subject_code,
                exam_year=placement_context.exam_year,
                english_track=placement_context.english_track,
                math_track=placement_context.math_track,
            )
            if not leaves:
                raise ValueError("syllabus missing for subject")
            placement_slots = build_placement_slots(
                db, placement_context, leaves, overview.weak_nodes
            )
            if question_count is None:
                question_count = len(placement_slots)
            else:
                placement_slots = placement_slots[:question_count]
                question_count = len(placement_slots)
            if question_count == 0:
                raise ValueError("placement paper template has no questions")
        else:
            leaves = self._leaf_nodes(db, subject_code)
            if not leaves:
                raise ValueError("syllabus missing for subject")
            if question_count is None:
                question_count = DEFAULT_QUESTION_COUNT

        target_nodes = self._pick_target_nodes(
            db, overview.weak_nodes, leaves, question_count
        )

        if purpose == "placement" and placement_slots is not None:
            if policy is None or policy.provider == "mock":
                out = self._mock_questions_from_slots(
                    student_user_id,
                    subject_code,
                    placement_slots,
                    placement_context=placement_context,
                )
                if on_progress:
                    on_progress(len(out), question_count, f"已生成 {len(out)}/{question_count} 题")
                return out

            batched = self._generate_with_llm_batches_from_slots(
                policy.provider,
                policy.model,
                policy.params or {},
                student_user_id=student_user_id,
                subject_code=subject_code,
                slots=placement_slots,
                placement_context=placement_context,
                on_progress=on_progress,
            )
            return batched

        if policy is None or policy.provider == "mock":
            out = self._mock_questions(
                student_user_id,
                subject_code,
                target_nodes,
                question_count,
                purpose=purpose,
            )
            if on_progress:
                on_progress(len(out), question_count, f"已生成 {len(out)}/{question_count} 题")
            return out

        batched = self._generate_with_llm_batches(
            policy.provider,
            policy.model,
            policy.params or {},
            student_user_id=student_user_id,
            subject_code=subject_code,
            target_nodes=target_nodes,
            question_count=question_count,
            purpose=purpose,
            on_progress=on_progress,
        )
        if batched:
            return batched

        out = self._deterministic_questions(
            student_user_id,
            subject_code,
            target_nodes,
            question_count,
            purpose=purpose,
        )
        if on_progress:
            on_progress(len(out), question_count, f"已生成 {len(out)}/{question_count} 题")
        return out

    def generate_prepared_placement(
        self,
        *,
        provider: str | None,
        model: str | None,
        params: dict | None,
        placement_context: PlacementGenContext,
        placement_slots: list[PlacementSlot],
        student_user_id: uuid.UUID,
        subject_code: str,
        on_progress: ProgressCallback | None = None,
    ) -> list[GeneratedQuestion]:
        question_count = len(placement_slots)
        if question_count == 0:
            raise ValueError("placement paper template has no questions")

        if provider is None or provider == "mock":
            out = self._mock_questions_from_slots(
                student_user_id,
                subject_code,
                placement_slots,
                placement_context=placement_context,
            )
            if on_progress:
                on_progress(len(out), question_count, f"已生成 {len(out)}/{question_count} 题")
            return out

        return self._generate_with_llm_batches_from_slots(
            provider,
            model or "",
            params or {},
            student_user_id=student_user_id,
            subject_code=subject_code,
            slots=placement_slots,
            placement_context=placement_context,
            on_progress=on_progress,
        )

    def generate_prepared_self_test(
        self,
        *,
        provider: str | None,
        model: str | None,
        params: dict | None,
        target_nodes: list[SyllabusNode],
        student_user_id: uuid.UUID,
        subject_code: str,
        question_count: int,
        on_progress: ProgressCallback | None = None,
    ) -> list[GeneratedQuestion]:
        if provider is None or provider == "mock":
            out = self._mock_questions(
                student_user_id,
                subject_code,
                target_nodes,
                question_count,
                purpose="self_test",
            )
            if on_progress:
                on_progress(len(out), question_count, f"已生成 {len(out)}/{question_count} 题")
            return out

        batched = self._generate_with_llm_batches(
            provider,
            model or "",
            params or {},
            student_user_id=student_user_id,
            subject_code=subject_code,
            target_nodes=target_nodes,
            question_count=question_count,
            purpose="self_test",
            on_progress=on_progress,
        )
        if batched:
            return batched

        out = self._deterministic_questions(
            student_user_id,
            subject_code,
            target_nodes,
            question_count,
            purpose="self_test",
        )
        if on_progress:
            on_progress(len(out), question_count, f"已生成 {len(out)}/{question_count} 题")
        return out

    def _generate_with_llm_batches_from_slots(
        self,
        provider: str,
        model: str,
        params: dict,
        *,
        student_user_id: uuid.UUID,
        subject_code: str,
        slots: list[PlacementSlot],
        placement_context: PlacementGenContext,
        on_progress: ProgressCallback | None = None,
    ) -> list[GeneratedQuestion]:
        question_count = len(slots)
        out: list[GeneratedQuestion] = []
        seq = 1
        while seq <= question_count:
            batch_count = min(LLM_BATCH_SIZE, question_count - seq + 1)
            batch_slots = slots[seq - 1 : seq - 1 + batch_count]
            batch = self._llm_questions_for_slot_batch(
                provider,
                model,
                params,
                subject_code=subject_code,
                batch_slots=batch_slots,
                placement_context=placement_context,
            )

            for item in batch:
                out.append(
                    GeneratedQuestion(
                        seq=seq,
                        knowledge_node_id=item.knowledge_node_id,
                        q_type=item.q_type,
                        stem=item.stem,
                        choices_json=item.choices_json,
                        answer_key=item.answer_key,
                        points=item.points,
                        rubric_json=item.rubric_json,
                    )
                )
                seq += 1
            if on_progress:
                on_progress(
                    min(seq - 1, question_count),
                    question_count,
                    f"已生成 {min(seq - 1, question_count)}/{question_count} 题",
                )
        return out

    def _llm_questions_for_slot_batch(
        self,
        provider: str,
        model: str,
        params: dict,
        *,
        subject_code: str,
        batch_slots: list[PlacementSlot],
        placement_context: PlacementGenContext,
    ) -> list[GeneratedQuestion]:
        parsed: list[GeneratedQuestion] = []
        batch_error: str | None = None
        try:
            raw = self._call_llm_for_slots(
                provider,
                model,
                params,
                subject_code=subject_code,
                slots=batch_slots,
                placement_context=placement_context,
            )
            maybe = self._parse_llm_questions_for_slots(raw, slots=batch_slots)
            if maybe:
                parsed = maybe
            else:
                batch_error = "LLM response could not be parsed"
        except Exception as exc:  # noqa: BLE001
            batch_error = str(exc)
            parsed = []

        if len(parsed) < len(batch_slots):
            for slot in batch_slots[len(parsed) :]:
                single, single_error = self._llm_question_for_single_slot(
                    provider,
                    model,
                    params,
                    subject_code=subject_code,
                    slot=slot,
                    placement_context=placement_context,
                )
                if single is None:
                    detail = single_error or batch_error or "unknown error"
                    raise ValueError(
                        f"LLM failed to generate placement question seq={slot.seq}: {detail}"
                    )
                parsed.append(single)
        return parsed

    def _llm_question_for_single_slot(
        self,
        provider: str,
        model: str,
        params: dict,
        *,
        subject_code: str,
        slot: PlacementSlot,
        placement_context: PlacementGenContext,
    ) -> tuple[GeneratedQuestion | None, str | None]:
        last_error: str | None = None
        for _ in range(2):
            try:
                raw = self._call_llm_for_slots(
                    provider,
                    model,
                    params,
                    subject_code=subject_code,
                    slots=[slot],
                    placement_context=placement_context,
                )
                parsed = self._parse_llm_questions_for_slots(raw, slots=[slot])
                if parsed:
                    return parsed[0], None
                last_error = "LLM response could not be parsed"
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
        return None, last_error

    def _generate_with_llm_batches(
        self,
        provider: str,
        model: str,
        params: dict,
        *,
        student_user_id: uuid.UUID,
        subject_code: str,
        target_nodes: list[SyllabusNode],
        question_count: int,
        purpose: PaperPurpose,
        on_progress: ProgressCallback | None = None,
    ) -> list[GeneratedQuestion]:
        out: list[GeneratedQuestion] = []
        seq = 1
        while seq <= question_count:
            batch_count = min(LLM_BATCH_SIZE, question_count - seq + 1)
            batch_nodes = [
                target_nodes[(seq - 1 + i) % len(target_nodes)] for i in range(batch_count)
            ]
            batch: list[GeneratedQuestion] = []
            try:
                raw = self._call_llm(
                    provider,
                    model,
                    params,
                    subject_code=subject_code,
                    target_nodes=batch_nodes,
                    question_count=batch_count,
                    purpose=purpose,
                )
                parsed = self._parse_llm_questions(
                    raw, target_nodes=batch_nodes, question_count=batch_count
                )
                if parsed:
                    batch = parsed
            except Exception:
                batch = []

            if not batch:
                batch = self._deterministic_questions(
                    student_user_id,
                    subject_code,
                    batch_nodes,
                    batch_count,
                    purpose=purpose,
                )

            for item in batch[:batch_count]:
                out.append(
                    GeneratedQuestion(
                        seq=seq,
                        knowledge_node_id=item.knowledge_node_id,
                        q_type=item.q_type,
                        stem=item.stem,
                        choices_json=item.choices_json,
                        answer_key=item.answer_key,
                        points=item.points,
                    )
                )
                seq += 1
            if on_progress:
                on_progress(min(seq - 1, question_count), question_count, f"已生成 {min(seq - 1, question_count)}/{question_count} 题")
        return out

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

    @staticmethod
    def _purpose_label(purpose: PaperPurpose) -> str:
        if purpose == "placement":
            return "模拟摸底卷"
        return "自测卷"

    def _schema_example_for_slot(self, slot: PlacementSlot) -> dict:
        base: dict = {
            "seq": slot.seq,
            "knowledge_node_id": str(slot.knowledge_node.id),
            "q_type": slot.q_type,
            "stem": "<完整题干，考生可直接作答>",
            "points": slot.points,
        }
        if slot.q_type == "multi_choice":
            base["choices"] = [
                {"key": "A", "text": "<选项>"},
                {"key": "B", "text": "<选项>"},
                {"key": "C", "text": "<选项>"},
                {"key": "D", "text": "<选项>"},
            ]
            base["answer_key"] = "AB"
        elif slot.q_type == "single_choice":
            base["choices"] = [
                {"key": "A", "text": "<选项>"},
                {"key": "B", "text": "<选项>"},
                {"key": "C", "text": "<选项>"},
                {"key": "D", "text": "<选项>"},
            ]
            base["answer_key"] = "A"
        elif slot.q_type == "fill_blank":
            base["answer_key"] = "<填空标准答案>"
        elif slot.q_type in ("short_answer", "essay"):
            base["answer_key"] = ""
            base["rubric_json"] = {
                "reference_answer": "<参考要点>",
                "keywords": ["<关键词>"],
            }
        return base

    def _call_llm_for_slots(
        self,
        provider: str,
        model: str,
        params: dict,
        *,
        subject_code: str,
        slots: list[PlacementSlot],
        placement_context: PlacementGenContext,
    ) -> str:
        slots_payload = [
            {
                "seq": slot.seq,
                "section_name": slot.section_name,
                "section_index": slot.section_index,
                "q_type": slot.q_type,
                "knowledge_node_id": str(slot.knowledge_node.id),
                "knowledge_node_name": slot.knowledge_node.name,
            }
            for slot in slots
        ]
        prompt_lines = [
            f"你是考研辅导命题老师。请为{self._purpose_label('placement')}生成试题。",
            f"试卷名称：{placement_context.paper_title}",
            f"科目代码：{subject_code}",
            f"考生目标考试年份：{placement_context.exam_year}",
            "请按往年真题卷的题型与题量结构出题，严格依据当年考试大纲，可参考往年真题风格但须原创题干。",
            "题干必须是完整、可独立作答的题目正文；禁止写「参照某年卷第几题」「卷面第几题」「请填写正确答案」等元数据或占位语。",
            "数学公式使用 LaTeX，并用 $...$ 包裹行内公式（例如 $\\theta$、$X_1$、$x^{\\theta-1}$）；分段函数可用 \\begin{cases}...\\end{cases}。",
            "当年考试大纲：",
            json.dumps(placement_context.syllabus_outline, ensure_ascii=False),
            "往年真题卷结构（题型与题量）：",
            json.dumps(placement_context.paper_sections, ensure_ascii=False),
        ]
        if placement_context.past_exam_samples:
            prompt_lines.extend(
                [
                    "往年真题样题（仅供风格参考）：",
                    json.dumps(placement_context.past_exam_samples, ensure_ascii=False),
                ]
            )
        prompt_lines.extend(
            [
                "本批次需生成的题目（按卷面顺序）：",
                json.dumps(slots_payload, ensure_ascii=False),
                "",
                "只输出 STRICT JSON，不要 markdown：",
                json.dumps(
                    {"questions": [self._schema_example_for_slot(slot) for slot in slots]},
                    ensure_ascii=False,
                ),
            ]
        )
        prompt = "\n".join(prompt_lines)
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

    def _call_llm(
        self,
        provider: str,
        model: str,
        params: dict,
        *,
        subject_code: str,
        target_nodes: list[SyllabusNode],
        question_count: int,
        purpose: PaperPurpose,
    ) -> str:
        nodes_payload = [
            {"id": str(n.id), "name": n.name} for n in target_nodes[:question_count]
        ]
        prompt_lines = [
            f"你是考研辅导命题老师。请为{self._purpose_label(purpose)}生成选择题。",
            f"科目代码：{subject_code}",
            f"需要题目数量：{question_count}",
            "优先覆盖以下知识点（薄弱点优先）：",
        ]

        prompt_lines.extend(
            [
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
        prompt = "\n".join(prompt_lines)
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

    @staticmethod
    def _extract_json_payload(raw: str) -> dict:
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("LLM response must be a JSON object")
        return data

    def _parse_llm_question_item(
        self,
        item: dict,
        *,
        slot: PlacementSlot,
        allowed_ids: set[uuid.UUID],
    ) -> GeneratedQuestion | None:
        stem = str(item.get("stem") or "").strip()
        if not stem:
            return None

        node_raw = item.get("knowledge_node_id")
        node_id: uuid.UUID | None = None
        if node_raw:
            try:
                node_id = uuid.UUID(str(node_raw))
            except ValueError:
                node_id = None
        if node_id is None or node_id not in allowed_ids:
            node_id = slot.knowledge_node.id

        q_type = slot.q_type
        if q_type in ("single_choice", "multi_choice"):
            choices = item.get("choices") or []
            if not choices:
                return None
            answer_key = str(item.get("answer_key") or "A").strip().upper()
            if q_type == "single_choice" and answer_key not in CHOICE_KEYS:
                answer_key = "A"
            choices_json = [
                {"key": str(c.get("key")), "text": str(c.get("text") or "")}
                for c in choices
                if c.get("key")
            ]
            return GeneratedQuestion(
                seq=slot.seq,
                knowledge_node_id=node_id,
                q_type=q_type,
                stem=stem,
                choices_json=choices_json,
                answer_key=answer_key,
                points=slot.points,
                rubric_json=None,
            )

        if q_type == "fill_blank":
            answer_key = str(item.get("answer_key") or "").strip()
            if not answer_key:
                return None
            return GeneratedQuestion(
                seq=slot.seq,
                knowledge_node_id=node_id,
                q_type=q_type,
                stem=stem,
                choices_json=None,
                answer_key=answer_key,
                points=slot.points,
                rubric_json=None,
            )

        if q_type in ("short_answer", "essay"):
            rubric_raw = item.get("rubric_json") or item.get("rubric")
            rubric_json = rubric_raw if isinstance(rubric_raw, dict) else {
                "reference_answer": str(item.get("answer_key") or stem),
                "keywords": [slot.knowledge_node.name, slot.section_name],
            }
            return GeneratedQuestion(
                seq=slot.seq,
                knowledge_node_id=node_id,
                q_type=q_type,
                stem=stem,
                choices_json=None,
                answer_key=str(item.get("answer_key") or "").strip(),
                points=slot.points,
                rubric_json=rubric_json,
            )

        return None

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

    def _parse_llm_questions_for_slots(
        self,
        raw: str,
        *,
        slots: list[PlacementSlot],
    ) -> list[GeneratedQuestion]:
        try:
            data = self._extract_json_payload(raw)
        except (json.JSONDecodeError, ValueError):
            return []
        items = data.get("questions") or []
        if not isinstance(items, list) or not items:
            return []

        allowed_ids = {slot.knowledge_node.id for slot in slots}
        out: list[GeneratedQuestion] = []
        for idx, slot in enumerate(slots):
            if idx >= len(items) or not isinstance(items[idx], dict):
                break
            parsed = self._parse_llm_question_item(
                items[idx], slot=slot, allowed_ids=allowed_ids
            )
            if parsed is None:
                return []
            out.append(parsed)
        return out

    @staticmethod
    def _answer_key(student_user_id: uuid.UUID, subject_code: str, seq: int) -> str:
        digest = hashlib.sha256(f"{student_user_id}:{subject_code}:{seq}".encode()).hexdigest()
        return CHOICE_KEYS[int(digest[:8], 16) % len(CHOICE_KEYS)]

    @staticmethod
    def _placement_stem_prefix(
        section_name: str,
        node_name: str,
        seq: int,
        placement_context: PlacementGenContext | None,
        node_id: uuid.UUID,
    ) -> str:
        if placement_context is None:
            return f"【模拟摸底·{section_name}·{node_name}】"
        ref_year = reference_year_for_node(placement_context, node_id, fallback_seq=seq)
        year_label = f"{placement_context.exam_year}考纲"
        if ref_year is not None:
            return (
                f"【模拟摸底·{section_name}·{year_label}·{node_name}·参照{ref_year}年卷】"
            )
        return f"【模拟摸底·{section_name}·{year_label}·{node_name}】"

    def _mock_stem_for_slot(
        self,
        slot: PlacementSlot,
        *,
        placement_context: PlacementGenContext | None,
    ) -> str:
        prefix = self._placement_stem_prefix(
            slot.section_name,
            slot.knowledge_node.name,
            slot.seq,
            placement_context,
            slot.knowledge_node.id,
        )
        type_hint = "（多选）" if slot.q_type == "multi_choice" else ""
        if slot.q_type == "fill_blank":
            prompt = f"请填写正确答案（卷面第{slot.seq}题）"
        elif slot.q_type in ("short_answer", "essay"):
            prompt = f"请作答（卷面第{slot.seq}题，满分{slot.points}分）"
        else:
            prompt = f"请选择最符合考纲要求的选项（卷面第{slot.seq}题）"
        return (
            f"{prefix}{type_hint}第{slot.section_index}题：{prompt}"
        )

    def _mock_payload_for_slot(
        self,
        student_user_id: uuid.UUID,
        subject_code: str,
        slot: PlacementSlot,
        *,
        placement_context: PlacementGenContext | None,
    ) -> tuple[str, list[dict] | None, str, dict | None]:
        node = slot.knowledge_node
        key = self._answer_key(student_user_id, subject_code, slot.seq)
        if slot.q_type == "fill_blank":
            return (
                self._mock_stem_for_slot(slot, placement_context=placement_context),
                None,
                key,
                None,
            )
        if slot.q_type in ("short_answer", "essay"):
            rubric = {
                "reference_answer": f"{node.name}相关参考要点",
                "keywords": [node.name, slot.section_name],
            }
            return (
                self._mock_stem_for_slot(slot, placement_context=placement_context),
                None,
                "",
                rubric,
            )
        if slot.q_type == "multi_choice":
            choices = [{"key": k, "text": f"{node.name}相关表述 {k}"} for k in CHOICE_KEYS]
            multi_key = "".join(sorted({key, CHOICE_KEYS[(CHOICE_KEYS.index(key) + 1) % len(CHOICE_KEYS)]}))
            return (
                self._mock_stem_for_slot(slot, placement_context=placement_context),
                choices,
                multi_key,
                None,
            )
        choices = [{"key": k, "text": f"{node.name}相关表述 {k}"} for k in CHOICE_KEYS]
        return (
            self._mock_stem_for_slot(slot, placement_context=placement_context),
            choices,
            key,
            None,
        )

    def _mock_questions_from_slots(
        self,
        student_user_id: uuid.UUID,
        subject_code: str,
        slots: list[PlacementSlot],
        *,
        placement_context: PlacementGenContext | None,
    ) -> list[GeneratedQuestion]:
        out: list[GeneratedQuestion] = []
        for slot in slots:
            stem, choices, key, rubric = self._mock_payload_for_slot(
                student_user_id, subject_code, slot, placement_context=placement_context
            )
            out.append(
                GeneratedQuestion(
                    seq=slot.seq,
                    knowledge_node_id=slot.knowledge_node.id,
                    q_type=slot.q_type,
                    stem=stem,
                    choices_json=choices,
                    answer_key=key,
                    points=slot.points,
                    rubric_json=rubric,
                )
            )
        return out

    def _deterministic_questions_from_slots(
        self,
        student_user_id: uuid.UUID,
        subject_code: str,
        slots: list[PlacementSlot],
        *,
        placement_context: PlacementGenContext | None,
    ) -> list[GeneratedQuestion]:
        out: list[GeneratedQuestion] = []
        for slot in slots:
            stem, choices, key, rubric = self._mock_payload_for_slot(
                student_user_id, subject_code, slot, placement_context=placement_context
            )
            out.append(
                GeneratedQuestion(
                    seq=slot.seq,
                    knowledge_node_id=slot.knowledge_node.id,
                    q_type=slot.q_type,
                    stem=stem,
                    choices_json=choices,
                    answer_key=key,
                    points=slot.points,
                    rubric_json=rubric,
                )
            )
        return out

    def _mock_stem(
        self,
        node_name: str,
        seq: int,
        purpose: PaperPurpose,
    ) -> str:
        return f"【薄弱巩固·{node_name}】请选择最符合考纲要求的选项（第{seq}题）"

    def _fallback_stem(
        self,
        node_name: str,
        seq: int,
        purpose: PaperPurpose,
    ) -> str:
        return f"【{node_name}】请选择最符合要求的选项（第{seq}题）"

    def _mock_questions(
        self,
        student_user_id: uuid.UUID,
        subject_code: str,
        target_nodes: list[SyllabusNode],
        question_count: int,
        *,
        purpose: PaperPurpose,
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
                    stem=self._mock_stem(node.name, seq, purpose),
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
        *,
        purpose: PaperPurpose,
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
                    stem=self._fallback_stem(node.name, seq, purpose),
                    choices_json=choices,
                    answer_key=key,
                    points=1,
                )
            )
        return out
