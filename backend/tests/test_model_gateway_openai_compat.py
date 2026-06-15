import json

import httpx

from app.services.model_gateway import ModelGateway, ModelGatewayRequest


def test_openai_compat_posts_chat_completions_and_returns_text():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path.endswith("/v1/chat/completions")
        body = json.loads(request.content.decode())
        assert body["model"] == "gpt-test"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "hello from provider"}}]},
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="https://example.invalid")

    gw = ModelGateway(http_client=client)
    out = gw.generate(
        ModelGatewayRequest(
            provider="openai_compat",
            model="gpt-test",
            scene="chat",
            prompt="hi",
            params={"base_url": "https://example.invalid", "api_key": "k"},
        )
    )
    assert out.text == "hello from provider"


def test_openai_compat_uses_compatible_mode_v1_suffix():
    seen_path = {"value": ""}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_path["value"] = request.url.path
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="https://example.invalid")
    gw = ModelGateway(http_client=client)
    gw.generate(
        ModelGatewayRequest(
            provider="openai_compat",
            model="gpt-test",
            scene="chat",
            prompt="hi",
            params={
                "base_url": "https://example.invalid/compatible-mode/v1",
                "api_key": "k",
            },
        )
    )
    assert seen_path["value"] == "/compatible-mode/v1/chat/completions"

