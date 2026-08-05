from app.models import (
    QuestionBankItem,
    SelfTestPaper,
    SelfTestQuestion,
    SelfTestSubmission,
    UserRole,
)
from app.services.self_test_assembler import SelfTestAssembler
from tests.factories import make_org, make_user


def _bank_item(db, *, creator, scope, org_id, stem, subject_code="english", status="active"):
    item = QuestionBankItem(
        scope=scope,
        org_id=org_id,
        subject_code=subject_code,
        knowledge_node_id=None,
        q_type="single_choice",
        stem=stem,
        choices_json=[{"key": "A", "text": "answer"}],
        answer_key="A",
        analysis_text=None,
        difficulty=2,
        source_type="admin_manual",
        status=status,
        created_by=creator.id,
    )
    db.add(item)
    db.flush()
    return item


def _people(db):
    org = make_org(db)
    admin = make_user(db, org, UserRole.org_admin)
    student = make_user(db, org, UserRole.student)
    return org, admin, student


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
