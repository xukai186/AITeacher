import json

from app.models import ModelPolicy, SyllabusNode
from app.services.question_enrichment import QuestionEnrichmentService
from tests.factories import make_org


def _suggest(service, db_session, org_id):
    return service.suggest(
        db_session,
        org_id=org_id,
        stem="Choose the correct tense: She ___ to school.",
        q_type="single_choice",
        choices_json=[{"key": "A", "text": "go"}, {"key": "B", "text": "goes"}],
        answer_key="B",
    )


def test_enrichment_heuristic_without_policy(db_session):
    org = make_org(db_session)
    db_session.commit()

    out = _suggest(QuestionEnrichmentService(), db_session, org.id)

    assert out.subject_code == "english"
    assert out.difficulty == 3
    assert out.knowledge_node_id is None
    assert out.analysis_text is None
    assert out.q_type is None


def test_enrichment_uses_policy_and_validates_output(db_session, monkeypatch):
    org = make_org(db_session)
    english_node = SyllabusNode(subject_code="english", name="Verb tense")
    math_node = SyllabusNode(subject_code="math", name="Calculus")
    policy = ModelPolicy(
        org_id=org.id,
        scene="paper_gen",
        provider="openai_compat",
        model="test-model",
        params={"temperature": 0},
    )
    db_session.add_all([english_node, math_node, policy])
    db_session.commit()
    calls = []

    def fake_call(self, provider, model, params, *, prompt):
        calls.append((provider, model, params, prompt))
        return json.dumps(
            {
                "subject_code": "english",
                "knowledge_node_id": str(math_node.id),
                "difficulty": 9,
                "analysis_text": "The third-person singular takes -s.",
                "q_type": "single_choice",
            }
        )

    monkeypatch.setattr(QuestionEnrichmentService, "_call_llm", fake_call)

    out = _suggest(QuestionEnrichmentService(), db_session, org.id)

    assert out.subject_code == "english"
    assert out.knowledge_node_id is None
    assert out.difficulty == 5
    assert out.analysis_text == "The third-person singular takes -s."
    assert out.q_type == "single_choice"
    assert calls[0][:3] == ("openai_compat", "test-model", {"temperature": 0})
    assert "Verb tense" in calls[0][3]


def test_enrichment_accepts_subject_matching_node(db_session, monkeypatch):
    org = make_org(db_session)
    node = SyllabusNode(subject_code="english", name="Verb tense")
    policy = ModelPolicy(
        org_id=org.id,
        scene="paper_gen",
        provider="openai_compat",
        model="test-model",
        params={},
    )
    db_session.add_all([node, policy])
    db_session.commit()

    monkeypatch.setattr(
        QuestionEnrichmentService,
        "_call_llm",
        lambda *args, **kwargs: json.dumps(
            {
                "subject_code": "english",
                "knowledge_node_id": str(node.id),
                "difficulty": 2,
                "analysis_text": None,
            }
        ),
    )

    out = _suggest(QuestionEnrichmentService(), db_session, org.id)

    assert out.knowledge_node_id == node.id
    assert out.difficulty == 2
