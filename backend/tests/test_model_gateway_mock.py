from app.services.model_gateway import ModelGateway, ModelGatewayRequest


def test_mock_provider_returns_deterministic_text():
    gw = ModelGateway()
    out1 = gw.generate(ModelGatewayRequest(provider="mock", model="mock-v1", scene="chat", prompt="hi"))
    out2 = gw.generate(ModelGatewayRequest(provider="mock", model="mock-v1", scene="chat", prompt="hi"))
    assert out1.text
    assert out1.text == out2.text

