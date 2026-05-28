from app.schemas.chat import ChatPostRequest
from app.schemas.model_policy import ModelPolicyUpsert


def test_model_policy_schema_roundtrip():
    obj = ModelPolicyUpsert(scene="chat", provider="mock", model="mock-v1", params={"x": 1})
    assert obj.scene == "chat"
    assert obj.params == {"x": 1}


def test_chat_post_request_validation():
    req = ChatPostRequest(agent_type="subject", subject_code="english", message="hi")
    assert req.agent_type == "subject"
    assert req.subject_code == "english"
