from __future__ import annotations

import base64
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MediaAsset, ModelPolicy
from app.services.model_gateway import ModelGateway


@dataclass(frozen=True)
class OCRQuestion:
    q_type: str
    stem: str
    choices: list[dict] | None
    answer_key: str | None


@dataclass(frozen=True)
class SegmentedQuestions:
    kind: Literal["segmented"]
    questions: list[OCRQuestion]


@dataclass(frozen=True)
class RawTextFallback:
    kind: Literal["raw_text_fallback"]
    raw_text: str


SegmentedOCRResult = SegmentedQuestions | RawTextFallback


class QuestionOCRService:
    def __init__(self, model_gateway: ModelGateway | None = None) -> None:
        self._gateway = model_gateway or ModelGateway()

    def extract(
        self,
        db: Session,
        *,
        org_id: uuid.UUID,
        asset_id: uuid.UUID,
    ) -> OCRQuestion:
        asset = self._load_asset(db, org_id=org_id, asset_id=asset_id)
        policy = self._load_policy(db, org_id=org_id)
        data = self._extract(Path(asset.storage_path), asset.content_type, policy)
        return self._validate(data)

    def extract_segmented(
        self,
        db: Session,
        *,
        org_id: uuid.UUID,
        asset_id: uuid.UUID,
    ) -> SegmentedOCRResult:
        asset = self._load_asset(db, org_id=org_id, asset_id=asset_id)
        policy = self._load_policy(db, org_id=org_id)
        data = self._extract_segmented(
            Path(asset.storage_path), asset.content_type, policy
        )
        return self._validate_segmented(data)

    def _load_asset(self, db, *, org_id, asset_id) -> MediaAsset:
        asset = db.execute(
            select(MediaAsset).where(
                MediaAsset.id == asset_id,
                MediaAsset.org_id == org_id,
            )
        ).scalar_one_or_none()
        if asset is None:
            raise LookupError("media asset not found")
        return asset

    def _load_policy(self, db, *, org_id) -> ModelPolicy | None:
        return db.execute(
            select(ModelPolicy).where(
                ModelPolicy.org_id == org_id,
                ModelPolicy.scene == "paper_gen",
            )
        ).scalar_one_or_none()

    def _extract(
        self,
        path: Path,
        content_type: str,
        policy: ModelPolicy | None,
    ) -> dict:
        if policy is None:
            raise RuntimeError("paper_gen model policy is not configured")

        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        completion = self._gateway.complete(
            provider=policy.provider,
            model=policy.model,
            scene="paper_gen",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Extract this single question. Return strict JSON with "
                                "q_type, stem, choices, and answer_key. choices must be "
                                "a list of {key,text} objects or null."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{content_type};base64,{encoded}",
                            },
                        },
                    ],
                }
            ],
            tools=None,
            params=policy.params or {},
        )
        return self._parse_json(completion.text or "")

    def _extract_segmented(
        self, path: Path, content_type: str, policy: ModelPolicy | None
    ) -> dict:
        if policy is None:
            raise RuntimeError("paper_gen model policy is not configured")
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        completion = self._gateway.complete(
            provider=policy.provider,
            model=policy.model,
            scene="paper_gen",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "This image may contain multiple independent exam questions. "
                                "If you can reliably split them, return strict JSON: "
                                '{"kind":"segmented","questions":[{q_type,stem,choices,answer_key},...]} '
                                "where choices is a list of {key,text} or null. "
                                "If you cannot reliably split, do NOT invent questions; "
                                'return {"kind":"raw_text_fallback","raw_text":"..."} with the best OCR text.'
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{content_type};base64,{encoded}"},
                        },
                    ],
                }
            ],
            tools=None,
            params=policy.params or {},
        )
        return self._parse_json(completion.text or "")

    @staticmethod
    def _parse_json(raw: str) -> dict:
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("OCR response must be a JSON object")
        return data

    @staticmethod
    def _validate(data: dict) -> OCRQuestion:
        stem = str(data.get("stem") or "").strip()
        q_type = str(data.get("q_type") or "").strip()
        choices = data.get("choices")
        answer_key = data.get("answer_key")
        if not stem or not q_type:
            raise ValueError("OCR response requires q_type and stem")
        if choices is not None and not isinstance(choices, list):
            raise ValueError("OCR choices must be a list or null")
        return OCRQuestion(
            q_type=q_type,
            stem=stem,
            choices=choices,
            answer_key=str(answer_key).strip() if answer_key is not None else None,
        )

    @staticmethod
    def _validate_segmented(data: dict) -> SegmentedOCRResult:
        kind = str(data.get("kind") or "").strip()
        if kind == "raw_text_fallback":
            raw_text = str(data.get("raw_text") or "").strip()
            if not raw_text:
                raise ValueError("raw_text_fallback requires raw_text")
            return RawTextFallback(kind="raw_text_fallback", raw_text=raw_text)
        if kind != "segmented":
            raise ValueError(
                "segmented OCR response requires kind segmented or raw_text_fallback"
            )
        questions_raw = data.get("questions")
        if not isinstance(questions_raw, list) or not questions_raw:
            raise ValueError("segmented OCR response requires non-empty questions")
        questions = [QuestionOCRService._validate(q) for q in questions_raw]
        return SegmentedQuestions(kind="segmented", questions=questions)
