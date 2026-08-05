import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import (
    MasterPlan,
    MasterPlanVersion,
    QuestionBankItem,
    SelfTestPaper,
    SelfTestQuestion,
    SelfTestSubmission,
    SyllabusNode,
    UserRole,
    WrongBookItem,
)
from app.services.paper_gen import (
    DEFAULT_QUESTION_COUNT,
    GeneratedQuestion,
    PaperGenService,
)
from app.services.report import ReportService
from app.services.self_test_assembler import SelfTestAssembler
from tests.factories import make_org, make_user


def _bank_item(
    db,
    *,
    creator,
    scope,
    org_id,
    stem,
    subject_code="english",
    status="active",
    knowledge_node_id=None,
    created_at=None,
):
    item = QuestionBankItem(
        scope=scope,
        org_id=org_id,
        subject_code=subject_code,
        knowledge_node_id=knowledge_node_id,
        q_type="single_choice",
        stem=stem,
        choices_json=[{"key": "A", "text": "answer"}],
        answer_key="A",
        analysis_text=None,
        difficulty=2,
        source_type="admin_manual",
        status=status,
        created_by=creator.id,
        created_at=created_at or datetime.now(UTC),
    )
    db.add(item)
    db.flush()
    return item


def _people(db):
    org = make_org(db)
    admin = make_user(db, org, UserRole.org_admin)
    student = make_user(db, org, UserRole.student)
    return org, admin, student


def _english_leaf(db):
    node = SyllabusNode(subject_code="english", name="English leaf")
    db.add(node)
    db.flush()
    return node


def _wrong_book_item(db, student_user_id, knowledge_node_id):
    item = WrongBookItem(
        student_user_id=student_user_id,
        subject_code="english",
        knowledge_node_id=knowledge_node_id,
        source_type="self_test",
        source_id=uuid.uuid4(),
        question_snapshot_json={},
        answer_snapshot_json={},
        correct_snapshot_json={},
    )
    db.add(item)
    db.flush()
    return item


def _seed_master_with_focus(db, student_user_id, subject_code, node_ids):
    plan = MasterPlan(student_user_id=student_user_id)
    db.add(plan)
    db.flush()
    version = MasterPlanVersion(
        plan_id=plan.id,
        version=1,
        source="ai",
        weekly_goals_json=[
            {
                "kind": "focus",
                "subject_code": subject_code,
                "syllabus_node_ids": [str(node_id) for node_id in node_ids],
                "title": "t",
                "description": "d",
            }
        ],
        daily_time_budget_json=[],
    )
    db.add(version)
    db.flush()
    plan.current_version_id = version.id
    db.flush()
    return plan


def test_weak_node_ids_from_overview(db_session):
    _, _, student = _people(db_session)
    node = _english_leaf(db_session)
    _wrong_book_item(db_session, student.id, node.id)
    db_session.commit()

    ids = SelfTestAssembler()._weak_node_ids(
        db_session,
        student_user_id=student.id,
        subject_code="english",
    )

    assert node.id in ids


def test_select_falls_back_to_l3_after_weak_resolution_failure(
    db_session, monkeypatch
):
    org, admin, student = _people(db_session)
    item = _bank_item(
        db_session,
        creator=admin,
        scope="org",
        org_id=org.id,
        stem="L3 fallback",
    )
    db_session.commit()
    transaction_failed = False
    original_execute = db_session.execute
    original_rollback = db_session.rollback

    def failing_overview(*_args, **_kwargs):
        nonlocal transaction_failed
        transaction_failed = True
        raise RuntimeError("report query failed")

    def execute_after_failure(*args, **kwargs):
        if transaction_failed:
            raise RuntimeError("transaction requires rollback")
        return original_execute(*args, **kwargs)

    def rollback():
        nonlocal transaction_failed
        transaction_failed = False
        return original_rollback()

    monkeypatch.setattr(ReportService, "overview", failing_overview)
    monkeypatch.setattr(db_session, "execute", execute_after_failure)
    monkeypatch.setattr(db_session, "rollback", rollback)

    selected = SelfTestAssembler().select_from_bank(
        db_session,
        org_id=org.id,
        student_user_id=student.id,
        subject_code="english",
        count=1,
    )

    assert [question.bank_item_id for question in selected] == [item.id]
    assert selected[0].selection_source == "bank_org"


def test_weekly_focus_node_ids_from_active_master(db_session):
    _, _, student = _people(db_session)
    node_id = uuid.uuid4()
    _seed_master_with_focus(db_session, student.id, "english", [node_id])
    db_session.commit()

    ids = SelfTestAssembler()._weekly_focus_node_ids(
        db_session,
        student_user_id=student.id,
        subject_code="english",
    )

    assert node_id in ids


def test_weekly_focus_ignores_other_subject(db_session):
    _, _, student = _people(db_session)
    math_id = uuid.uuid4()
    _seed_master_with_focus(db_session, student.id, "math", [math_id])
    db_session.commit()

    ids = SelfTestAssembler()._weekly_focus_node_ids(
        db_session,
        student_user_id=student.id,
        subject_code="english",
    )

    assert math_id not in ids


def test_select_prefers_weak_then_focus_then_other(db_session):
    org, admin, student = _people(db_session)
    weak_node = _english_leaf(db_session)
    focus_node = _english_leaf(db_session)
    other_node = _english_leaf(db_session)
    _wrong_book_item(db_session, student.id, weak_node.id)
    _seed_master_with_focus(db_session, student.id, "english", [focus_node.id])
    now = datetime.now(UTC)

    other_item = _bank_item(
        db_session,
        creator=admin,
        scope="org",
        org_id=org.id,
        stem="Other",
        knowledge_node_id=other_node.id,
        created_at=now - timedelta(minutes=2),
    )
    null_item = _bank_item(
        db_session,
        creator=admin,
        scope="org",
        org_id=org.id,
        stem="Null",
        created_at=now - timedelta(minutes=1),
    )
    weak_item = _bank_item(
        db_session,
        creator=admin,
        scope="org",
        org_id=org.id,
        stem="Weak",
        knowledge_node_id=weak_node.id,
    )
    focus_item = _bank_item(
        db_session,
        creator=admin,
        scope="org",
        org_id=org.id,
        stem="Focus",
        knowledge_node_id=focus_node.id,
    )
    db_session.commit()

    picked = SelfTestAssembler().select_from_bank(
        db_session,
        org_id=org.id,
        student_user_id=student.id,
        subject_code="english",
        count=3,
    )

    assert [question.bank_item_id for question in picked] == [
        weak_item.id,
        focus_item.id,
        other_item.id,
    ]
    assert null_item.id not in {question.bank_item_id for question in picked}


def test_null_node_only_in_l3_when_weak_fills(db_session):
    org, admin, student = _people(db_session)
    weak_node = _english_leaf(db_session)
    _wrong_book_item(db_session, student.id, weak_node.id)
    null_item = _bank_item(
        db_session,
        creator=admin,
        scope="org",
        org_id=org.id,
        stem="Null",
    )
    weak_items = [
        _bank_item(
            db_session,
            creator=admin,
            scope="org",
            org_id=org.id,
            stem=f"Weak {index}",
            knowledge_node_id=weak_node.id,
        )
        for index in range(2)
    ]
    db_session.commit()

    picked = SelfTestAssembler().select_from_bank(
        db_session,
        org_id=org.id,
        student_user_id=student.id,
        subject_code="english",
        count=2,
    )

    assert {question.bank_item_id for question in picked} == {
        item.id for item in weak_items
    }
    assert null_item.id not in {question.bank_item_id for question in picked}


def test_org_before_global_within_weak_layer(db_session):
    org, admin, student = _people(db_session)
    weak_node = _english_leaf(db_session)
    _wrong_book_item(db_session, student.id, weak_node.id)
    global_item = _bank_item(
        db_session,
        creator=admin,
        scope="global",
        org_id=None,
        stem="Global weak",
        knowledge_node_id=weak_node.id,
    )
    org_item = _bank_item(
        db_session,
        creator=admin,
        scope="org",
        org_id=org.id,
        stem="Org weak",
        knowledge_node_id=weak_node.id,
    )
    db_session.commit()

    picked = SelfTestAssembler().select_from_bank(
        db_session,
        org_id=org.id,
        student_user_id=student.id,
        subject_code="english",
        count=1,
    )

    assert picked[0].bank_item_id == org_item.id
    assert picked[0].bank_item_id != global_item.id
    assert picked[0].selection_source == "bank_org"


def test_selects_active_org_items_before_active_global_items(db_session):
    org, admin, student = _people(db_session)
    org_items = [
        _bank_item(
            db_session,
            creator=admin,
            scope="org",
            org_id=org.id,
            stem=f"Org {index}",
        )
        for index in range(2)
    ]
    global_items = [
        _bank_item(
            db_session,
            creator=admin,
            scope="global",
            org_id=None,
            stem=f"Global {index}",
        )
        for index in range(2)
    ]
    _bank_item(
        db_session,
        creator=admin,
        scope="org",
        org_id=org.id,
        stem="Disabled",
        status="disabled",
    )
    _bank_item(
        db_session,
        creator=admin,
        scope="global",
        org_id=None,
        stem="Wrong subject",
        subject_code="math",
    )

    selected = SelfTestAssembler().select_from_bank(
        db_session,
        org_id=org.id,
        student_user_id=student.id,
        subject_code="english",
        count=3,
    )

    assert {question.bank_item_id for question in selected[:2]} == {
        item.id for item in org_items
    }
    assert selected[2].bank_item_id in {item.id for item in global_items}
    assert [question.selection_source for question in selected] == [
        "bank_org",
        "bank_org",
        "bank_global",
    ]
    assert [question.seq for question in selected] == [1, 2, 3]


def test_excludes_submitted_and_explicit_bank_item_ids(db_session):
    org, admin, student = _people(db_session)
    submitted_item = _bank_item(
        db_session,
        creator=admin,
        scope="org",
        org_id=org.id,
        stem="Already submitted",
    )
    fresh_org_item = _bank_item(
        db_session,
        creator=admin,
        scope="org",
        org_id=org.id,
        stem="Fresh org",
    )
    explicitly_excluded = _bank_item(
        db_session,
        creator=admin,
        scope="global",
        org_id=None,
        stem="Explicitly excluded",
    )
    fresh_global_item = _bank_item(
        db_session,
        creator=admin,
        scope="global",
        org_id=None,
        stem="Fresh global",
    )
    paper = SelfTestPaper(
        student_user_id=student.id,
        subject_code="english",
        source="bank",
        status="submitted",
    )
    db_session.add(paper)
    db_session.flush()
    db_session.add(
        SelfTestQuestion(
            paper_id=paper.id,
            seq=1,
            q_type=submitted_item.q_type,
            stem=submitted_item.stem,
            choices_json=submitted_item.choices_json,
            answer_key=submitted_item.answer_key,
            points=1,
            bank_item_id=submitted_item.id,
            selection_source="bank_org",
        )
    )
    db_session.add(
        SelfTestSubmission(
            paper_id=paper.id,
            student_user_id=student.id,
            status="submitted",
        )
    )
    db_session.flush()

    selected = SelfTestAssembler().select_from_bank(
        db_session,
        org_id=org.id,
        student_user_id=student.id,
        subject_code="english",
        count=4,
        exclude_bank_ids={explicitly_excluded.id},
    )

    assert [question.bank_item_id for question in selected] == [
        fresh_org_item.id,
        fresh_global_item.id,
    ]
    assert [question.selection_source for question in selected] == [
        "bank_org",
        "bank_global",
    ]


def test_assemble_fills_empty_bank_with_pending_ai_question(
    db_session, monkeypatch
):
    org = make_org(db_session)
    student = make_user(db_session, org, UserRole.student)

    def fake_generate_prepared_self_test(_self, **kwargs):
        assert kwargs["question_count"] == 1
        assert not db_session.in_transaction()
        return [
            GeneratedQuestion(
                seq=1,
                knowledge_node_id=None,
                q_type="single_choice",
                stem="AI fallback question",
                choices_json=[{"key": "A", "text": "answer"}],
                answer_key="A",
                points=2,
            )
        ]

    monkeypatch.setattr(
        PaperGenService,
        "generate_prepared_self_test",
        fake_generate_prepared_self_test,
    )

    assembled = SelfTestAssembler().assemble(
        db_session,
        org_id=org.id,
        student_user_id=student.id,
        subject_code="english",
        question_count=1,
        provider="mock-provider",
        model="mock-model",
        params={"temperature": 0},
        target_nodes=[],
    )

    bank_item = db_session.execute(select(QuestionBankItem)).scalar_one()
    assert bank_item.scope == "org"
    assert bank_item.org_id == org.id
    assert bank_item.source_type == "ai_generated"
    assert bank_item.status == "pending_review"
    assert bank_item.created_by == student.id
    assert len(assembled) == 1
    assert assembled[0].bank_item_id == bank_item.id
    assert assembled[0].selection_source == "ai_fallback"
    assert assembled[0].seq == 1


def test_assemble_uses_weak_bank_without_llm(db_session, monkeypatch):
    org, admin, student = _people(db_session)
    weak_node = _english_leaf(db_session)
    _wrong_book_item(db_session, student.id, weak_node.id)
    [
        _bank_item(
            db_session,
            creator=admin,
            scope="org",
            org_id=org.id,
            stem=f"Weak {index}",
            knowledge_node_id=weak_node.id,
        )
        for index in range(DEFAULT_QUESTION_COUNT)
    ]
    db_session.commit()

    def boom(*_args, **_kwargs):
        raise AssertionError("LLM should not be called")

    monkeypatch.setattr(PaperGenService, "generate_prepared_self_test", boom)

    assembled = SelfTestAssembler().assemble(
        db_session,
        org_id=org.id,
        student_user_id=student.id,
        subject_code="english",
        question_count=DEFAULT_QUESTION_COUNT,
        provider=None,
        model=None,
        params=None,
        target_nodes=[],
    )

    assert len(assembled) == DEFAULT_QUESTION_COUNT
    assert all(question.selection_source == "bank_org" for question in assembled)


def test_assemble_replaces_inactive_exact_duplicate(db_session, monkeypatch):
    org, admin, student = _people(db_session)
    inactive = _bank_item(
        db_session,
        creator=admin,
        scope="org",
        org_id=org.id,
        stem="Previously rejected question",
        status="rejected",
    )

    monkeypatch.setattr(
        PaperGenService,
        "generate_prepared_self_test",
        lambda _self, **_kwargs: [
            GeneratedQuestion(
                seq=1,
                knowledge_node_id=None,
                q_type="single_choice",
                stem=inactive.stem,
                choices_json=inactive.choices_json,
                answer_key=inactive.answer_key,
                points=1,
            )
        ],
    )

    assembled = SelfTestAssembler().assemble(
        db_session,
        org_id=org.id,
        student_user_id=student.id,
        subject_code="english",
        question_count=1,
        provider="mock-provider",
        model="mock-model",
        params={},
        target_nodes=[],
    )

    bank_items = db_session.execute(select(QuestionBankItem)).scalars().all()
    assert len(bank_items) == 2
    assert assembled[0].bank_item_id != inactive.id
    assert next(
        item for item in bank_items if item.id == assembled[0].bank_item_id
    ).status == "pending_review"

    assembled_again = SelfTestAssembler().assemble(
        db_session,
        org_id=org.id,
        student_user_id=student.id,
        subject_code="english",
        question_count=1,
        provider="mock-provider",
        model="mock-model",
        params={},
        target_nodes=[],
    )

    assert assembled_again[0].bank_item_id == assembled[0].bank_item_id
    assert len(db_session.execute(select(QuestionBankItem)).scalars().all()) == 2
