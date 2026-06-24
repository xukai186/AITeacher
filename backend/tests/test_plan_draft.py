import json
from datetime import datetime, timezone
from datetime import date

from app.models import MasterPlanVersion, ModelPolicy, StudentExamProfile, SubjectPlanVersion, UserRole
from app.seed_exam_majors import seed_exam_majors
from app.services.model_gateway import ModelGateway, ModelGatewayRequest, ModelGatewayResponse
from app.services.plan_draft import PlanDraftService
from app.services.planning import PlanningService
from tests.factories import make_org, make_user
from tests.test_placement_flow import _seed_student


def test_plan_draft_rules_includes_weekly_goals(db_session):
    student = _seed_student(db_session)
    org_id = student.org_id

    draft = PlanDraftService().draft_initial_plans(
        db_session,
        student_user_id=student.id,
        org_id=org_id,
        subject_codes=["english"],
    )
    assert draft.weekly_goals_json
    assert len(draft.daily_time_budget_json) == 7
    assert "english" in draft.subject_phases_json
    assert draft.subject_phases_json["english"][0]["title"]


def test_plan_draft_uses_llm_when_planning_policy_configured(db_session, monkeypatch):
    student = _seed_student(db_session)
    org_id = student.org_id
    db_session.add(
        ModelPolicy(
            org_id=org_id,
            scene="planning",
            provider="openai_compat",
            model="gpt-test",
            params={"base_url": "https://example.invalid", "api_key": "k"},
        )
    )
    db_session.commit()

    payload = {
        "weekly_goals": [
            {"title": "英语阅读强化", "description": "每天精读一篇并复盘错题。"}
        ],
        "daily_time_budget": [
            {"date": "2026-06-01", "minutes": 200},
            {"date": "2026-06-02", "minutes": 200},
        ],
        "subjects": {
            "english": {
                "phases": [
                    {"title": "阅读专项", "days": 7, "notes": "重点长难句与主旨题"}
                ]
            }
        },
    }

    class FakeGateway(ModelGateway):
        def generate(self, req: ModelGatewayRequest) -> ModelGatewayResponse:
            assert req.scene == "planning"
            return ModelGatewayResponse(text=json.dumps(payload, ensure_ascii=False))

    svc = PlanDraftService(model_gateway=FakeGateway())
    draft = svc.draft_initial_plans(
        db_session,
        student_user_id=student.id,
        org_id=org_id,
        subject_codes=["english"],
        today=date(2026, 6, 1),
    )
    assert draft.weekly_goals_json[0]["title"] == "英语阅读强化"
    assert draft.daily_time_budget_json[0]["minutes"] == 200
    assert draft.subject_phases_json["english"][0]["title"] == "阅读专项"


def test_create_initial_plans_persists_llm_draft(db_session, monkeypatch):
    student = _seed_student(db_session)
    org_id = student.org_id
    db_session.add(
        ModelPolicy(
            org_id=org_id,
            scene="planning",
            provider="openai_compat",
            model="gpt-test",
            params={},
        )
    )
    db_session.commit()

    payload = {
        "weekly_goals": [{"title": "周目标", "description": "说明"}],
        "daily_time_budget": [{"date": "2026-06-01", "minutes": 150}],
        "subjects": {
            "english": {"phases": [{"title": "基础", "days": 7, "notes": "notes"}]}
        },
    }

    class FakeGateway(ModelGateway):
        def generate(self, req: ModelGatewayRequest) -> ModelGatewayResponse:
            return ModelGatewayResponse(text=json.dumps(payload, ensure_ascii=False))

    monkeypatch.setattr(
        "app.services.planning.PlanDraftService",
        lambda *args, **kwargs: PlanDraftService(model_gateway=FakeGateway()),
    )

    PlanningService().create_initial_plans(db_session, student_user_id=student.id)
    db_session.commit()

    master_ver = db_session.query(MasterPlanVersion).one()
    assert master_ver.weekly_goals_json[0]["title"] == "周目标"
    subject_ver = db_session.query(SubjectPlanVersion).one()
    assert subject_ver.phases_json[0]["title"] == "基础"


def test_draft_initial_plans_uses_math_none_for_management_major(db_session):
    seed_exam_majors(db_session)
    org = make_org(db_session)
    student = make_user(
        db_session,
        org,
        role=UserRole.student,
        email="mba-math-none@demo.example",
    )
    db_session.add(
        StudentExamProfile(
            user_id=student.id,
            major_category_code="management_joint",
            major_code="mba_joint",
            english_track="english_2",
            math_track="none",
            subject_codes=["english", "politics"],
            cet_status="cet6",
            math_mastery_level="zero",
            profile_completed_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    draft = PlanDraftService().draft_initial_plans(
        db_session,
        student_user_id=student.id,
        org_id=org.id,
        subject_codes=["english", "math", "politics"],
    )
    assert "math" not in draft.subject_phases_json
