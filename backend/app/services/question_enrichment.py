from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ModelPolicy, SyllabusNode
from app.services.model_gateway import ModelGateway, ModelGatewayRequest


@dataclass(frozen=True)
class EnrichmentSuggestion:
    subject_code: str
    knowledge_node_id: uuid.UUID | None
    difficulty: int
    analysis_text: str | None
    q_type: str | None


class QuestionEnrichmentService:
    def __init__(self, model_gateway: ModelGateway | None = None) -> None:
        self._gateway = model_gateway or ModelGateway()

    def suggest(
        self,
        db: Session,
        *,
        org_id: uuid.UUID,
        stem: str,
        q_type: str,
        choices_json: list | None,
        answer_key: str | None,
    ) -> EnrichmentSuggestion:
        fallback = self._heuristic(stem)
        policy = self._policy(db, org_id)
        if policy is None:
            return fallback

        nodes = db.execute(select(SyllabusNode).order_by(SyllabusNode.name)).scalars().all()
        prompt = self._prompt(
            stem=stem,
            q_type=q_type,
            choices_json=choices_json,
            answer_key=answer_key,
            nodes=nodes,
        )
        try:
            raw = self._call_llm(
                policy.provider,
                policy.model,
                policy.params or {},
                prompt=prompt,
            )
            data = self._parse_json(raw)
        except (json.JSONDecodeError, TypeError, ValueError):
            return fallback

        subject_code = str(data.get("subject_code") or fallback.subject_code).strip()
        if not subject_code:
            subject_code = fallback.subject_code
        difficulty = self._difficulty(data.get("difficulty"))
        node_id = self._valid_node_id(db, data.get("knowledge_node_id"), subject_code)
        analysis_text = self._optional_text(data.get("analysis_text"))
        suggested_q_type = self._optional_text(data.get("q_type"))
        return EnrichmentSuggestion(
            subject_code=subject_code,
            knowledge_node_id=node_id,
            difficulty=difficulty,
            analysis_text=analysis_text,
            q_type=suggested_q_type,
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
    def _heuristic(stem: str) -> EnrichmentSuggestion:
        lowered = stem.lower()
        if any(word in lowered for word in ("数学", "函数", "方程", "积分", "导数", "math")):
            subject_code = "math"
        elif any(word in lowered for word in ("政治", "马克思", "毛泽东", "politics")):
            subject_code = "politics"
        else:
            subject_code = "english"
        return EnrichmentSuggestion(
            subject_code=subject_code,
            knowledge_node_id=None,
            difficulty=3,
            analysis_text=None,
            q_type=None,
        )

    @staticmethod
    def _prompt(
        *,
        stem: str,
        q_type: str,
        choices_json: list | None,
        answer_key: str | None,
        nodes: list[SyllabusNode],
    ) -> str:
        question = {
            "stem": stem,
            "q_type": q_type,
            "choices": choices_json,
            "answer_key": answer_key,
        }
        node_options = [
            {
                "id": str(node.id),
                "subject_code": node.subject_code,
                "name": node.name,
            }
            for node in nodes
        ]
        schema = {
            "subject_code": "english",
            "knowledge_node_id": "<uuid or null>",
            "difficulty": 3,
            "analysis_text": "<analysis or null>",
            "q_type": "<optional corrected type or null>",
        }
        return "\n".join(
            [
                "请根据题面补全题库属性。难度必须为 1-5。",
                "知识点只能从候选列表选择，且必须属于建议科目。",
                f"题面：{json.dumps(question, ensure_ascii=False)}",
                f"知识点候选：{json.dumps(node_options, ensure_ascii=False)}",
                "只输出 STRICT JSON，不要 markdown：",
                json.dumps(schema, ensure_ascii=False),
            ]
        )

    def _call_llm(
        self,
        provider: str,
        model: str,
        params: dict,
        *,
        prompt: str,
    ) -> str:
        response = self._gateway.generate(
            ModelGatewayRequest(
                provider=provider,
                model=model,
                scene="paper_gen",
                prompt=prompt,
                params=params,
            )
        )
        return response.text

    @staticmethod
    def _parse_json(raw: str) -> dict:
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("LLM response must be a JSON object")
        return data

    @staticmethod
    def _difficulty(value: object) -> int:
        try:
            difficulty = int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            difficulty = 3
        return min(5, max(1, difficulty))

    @staticmethod
    def _valid_node_id(
        db: Session,
        raw_node_id: object,
        subject_code: str,
    ) -> uuid.UUID | None:
        try:
            node_id = uuid.UUID(str(raw_node_id))
        except (TypeError, ValueError):
            return None
        node = db.get(SyllabusNode, node_id)
        if node is None or node.subject_code != subject_code:
            return None
        return node.id

    @staticmethod
    def _optional_text(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
