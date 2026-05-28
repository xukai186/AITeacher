from __future__ import annotations

import hashlib
from dataclasses import dataclass

import httpx


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
    def __init__(self, http_client: httpx.Client | None = None) -> None:
        self._http_client = http_client or httpx.Client()

    def generate(self, req: ModelGatewayRequest) -> ModelGatewayResponse:
        if req.provider == "mock":
            digest = hashlib.sha256(f"{req.model}:{req.scene}:{req.prompt}".encode("utf-8")).hexdigest()[:8]
            return ModelGatewayResponse(text=f"[mock:{req.scene}:{digest}] {req.prompt}")
        if req.provider == "openai_compat":
            params = req.params or {}
            base_url = params.get("base_url")
            api_key = params.get("api_key")
            if not base_url or not api_key:
                raise ValueError("openai_compat requires params.base_url and params.api_key")

            url = f"{base_url.rstrip('/')}/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}"}
            payload = {
                "model": req.model,
                "messages": [{"role": "user", "content": req.prompt}],
            }
            resp = self._http_client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            return ModelGatewayResponse(text=text)
        raise ValueError(f"unknown provider: {req.provider}")

