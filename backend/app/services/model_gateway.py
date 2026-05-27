from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelGatewayRequest:
    provider: str
    model: str
    scene: str
    prompt: str
    params: dict | None = None


@dataclass(frozen=True)
class ModelGatewayResponse:
    text: str


class ModelGateway:
    def generate(self, req: ModelGatewayRequest) -> ModelGatewayResponse:
        if req.provider == "mock":
            digest = hashlib.sha256(f"{req.model}:{req.scene}:{req.prompt}".encode("utf-8")).hexdigest()[:8]
            return ModelGatewayResponse(text=f"[mock:{req.scene}:{digest}] {req.prompt}")
        raise ValueError(f"unknown provider: {req.provider}")

