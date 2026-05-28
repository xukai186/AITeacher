from __future__ import annotations

import json

from app.models import SelfTestQuestion
from app.services.model_gateway import ModelGateway, ModelGatewayRequest


class GradingService:
    def __init__(self, model_gateway: ModelGateway | None = None) -> None:
        self._gw = model_gateway or ModelGateway()

    @staticmethod
    def grade_objective(question: SelfTestQuestion, content: str) -> tuple[int, bool]:
        key = (question.answer_key or "").strip()
        is_correct = content.strip() == key if key else False
        score = int(question.points) if is_correct else 0
        return score, is_correct

    def grade_subjective(self, question: SelfTestQuestion, content: str) -> tuple[int, dict]:
        prompt = "\n".join(
            [
                "You are an exam grader. Return STRICT JSON only.",
                f"Question: {question.stem}",
                f"Rubric JSON: {json.dumps(question.rubric_json or {}, ensure_ascii=False)}",
                f"Student answer: {content}",
                f"Max points: {int(question.points)}",
                "",
                'Output JSON schema: {"score": <int>, "feedback": <string>}',
            ]
        )
        resp = self._gw.generate(
            ModelGatewayRequest(
                provider="mock",
                model="mock-v1",
                scene="grading",
                prompt=prompt,
                params={},
            )
        )
        try:
            data = json.loads(resp.text)
        except Exception:
            data = {"score": 0, "feedback": resp.text}

        score_raw = data.get("score", 0)
        try:
            score = int(score_raw)
        except Exception:
            score = 0
        score = max(0, min(int(question.points), score))
        feedback = str(data.get("feedback", ""))
        return score, {"mode": "subjective", "feedback": feedback, "raw": data}

