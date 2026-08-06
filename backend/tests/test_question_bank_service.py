import uuid

import pytest
from fastapi import HTTPException

from app.models import UserRole
from app.schemas.question_bank import QuestionBankCreate
from app.services.question_bank import QuestionBankService
from tests.factories import make_org, make_user


def _admin(db_session):
    org = make_org(db_session)
    return make_user(db_session, org, UserRole.org_admin), org


def _staff(db_session, org):
    return make_user(db_session, org, UserRole.org_staff)


def _create(svc, db_session, actor, **overrides):
    values = {
        "scope": "org",
        "org_id": actor.org_id,
        "subject_code": "english",
        "knowledge_node_id": None,
        "q_type": "single_choice",
        "stem": f"What is X? {uuid.uuid4()}",
        "choices_json": [{"key": "A", "text": "1"}, {"key": "B", "text": "2"}],
        "answer_key": "A",
        "analysis_text": None,
        "difficulty": 2,
        "source_type": "admin_manual",
    }
    values.update(overrides)
    return svc.create(db_session, actor=actor, **values)


def test_manual_create_is_active(db_session):
    admin, org = _admin(db_session)
    item = _create(
        QuestionBankService(),
        db_session,
        admin,
        stem="What is X?",
    )
    db_session.commit()

    assert item.status == "active"
    assert item.org_id == org.id
    assert item.created_by == admin.id


def test_create_accepts_payload_schema(db_session):
    admin, org = _admin(db_session)
    payload = QuestionBankCreate(
        scope="org",
        org_id=org.id,
        subject_code="english",
        knowledge_node_id=None,
        q_type="short_answer",
        stem="Explain payload support",
        choices_json=None,
        answer_key="reference",
        analysis_text=None,
        difficulty=2,
        source_type="admin_manual",
    )

    item = QuestionBankService().create(db_session, actor=admin, payload=payload)

    assert item.stem == "Explain payload support"
    assert item.status == "active"


@pytest.mark.parametrize("source_type", ["ocr_import", "ai_generated"])
def test_imported_or_generated_create_is_pending_review(db_session, source_type):
    admin, _ = _admin(db_session)

    item = _create(
        QuestionBankService(),
        db_session,
        admin,
        source_type=source_type,
    )

    assert item.status == "pending_review"


def test_exact_duplicate_detected_after_stem_strip(db_session):
    admin, org = _admin(db_session)
    svc = QuestionBankService()
    original = _create(svc, db_session, admin, stem="  Same stem  ")
    db_session.commit()

    duplicate = svc.find_exact_duplicate(
        db_session,
        scope="org",
        org_id=org.id,
        q_type="single_choice",
        stem="Same stem",
    )

    assert duplicate is not None
    assert duplicate.id == original.id
    assert original.stem == "Same stem"


def test_create_rejects_exact_duplicate(db_session):
    admin, _ = _admin(db_session)
    svc = QuestionBankService()
    _create(svc, db_session, admin, stem="Same stem")

    with pytest.raises(HTTPException) as exc:
        _create(svc, db_session, admin, stem=" Same stem ")

    assert exc.value.status_code == 409


def test_duplicate_lookup_prefers_reusable_row_when_inactive_twin_exists(db_session):
    admin, org = _admin(db_session)
    svc = QuestionBankService()
    inactive = _create(
        svc,
        db_session,
        admin,
        stem="Repeated AI stem",
        source_type="ai_generated",
    )
    svc.reject(db_session, actor=admin, item_id=inactive.id)
    reusable = _create(
        svc,
        db_session,
        admin,
        stem="Repeated AI stem",
        source_type="ai_generated",
        allow_inactive_duplicate=True,
    )
    db_session.flush()

    duplicate = svc.find_exact_duplicate(
        db_session,
        scope="org",
        org_id=org.id,
        q_type="single_choice",
        stem="Repeated AI stem",
    )

    assert duplicate is not None
    assert duplicate.id == reusable.id
    with pytest.raises(HTTPException) as exc:
        _create(svc, db_session, admin, stem="Repeated AI stem")
    assert exc.value.status_code == 409


def test_approve_pending_ai_item(db_session):
    admin, _ = _admin(db_session)
    svc = QuestionBankService()
    item = _create(
        svc,
        db_session,
        admin,
        q_type="short_answer",
        stem="Explain Y",
        choices_json=None,
        answer_key="ref",
        difficulty=3,
        source_type="ai_generated",
    )
    db_session.commit()

    approved = svc.approve(db_session, actor=admin, item_id=item.id)
    db_session.commit()

    assert approved.status == "active"
    assert approved.reviewed_by == admin.id
    assert approved.reviewed_at is not None


def test_reject_and_disable_enforce_state_transitions(db_session):
    admin, _ = _admin(db_session)
    svc = QuestionBankService()
    pending = _create(svc, db_session, admin, source_type="ocr_import")
    active = _create(svc, db_session, admin, source_type="admin_manual")

    rejected = svc.reject(db_session, actor=admin, item_id=pending.id)
    disabled = svc.disable(db_session, actor=admin, item_id=active.id)

    assert rejected.status == "rejected"
    assert rejected.reviewed_by == admin.id
    assert disabled.status == "disabled"
    with pytest.raises(HTTPException) as approve_exc:
        svc.approve(db_session, actor=admin, item_id=active.id)
    with pytest.raises(HTTPException) as disable_exc:
        svc.disable(db_session, actor=admin, item_id=pending.id)
    assert approve_exc.value.status_code == 409
    assert disable_exc.value.status_code == 409


def test_staff_cannot_create_or_mutate_global_items(db_session):
    admin, org = _admin(db_session)
    staff = _staff(db_session, org)
    svc = QuestionBankService()
    global_item = _create(
        svc,
        db_session,
        admin,
        scope="global",
        org_id=None,
        source_type="ai_generated",
    )

    with pytest.raises(HTTPException) as create_exc:
        _create(
            svc,
            db_session,
            staff,
            scope="global",
            org_id=None,
            source_type="staff_manual",
        )
    with pytest.raises(HTTPException) as approve_exc:
        svc.approve(db_session, actor=staff, item_id=global_item.id)

    assert create_exc.value.status_code == 403
    assert approve_exc.value.status_code == 403


def test_list_visibility_and_filters(db_session):
    admin, org = _admin(db_session)
    staff = _staff(db_session, org)
    other_org = make_org(db_session, "Other Org")
    other_admin = make_user(db_session, other_org, UserRole.org_admin)
    svc = QuestionBankService()
    own_active = _create(svc, db_session, admin, subject_code="english")
    own_pending = _create(
        svc,
        db_session,
        admin,
        subject_code="math",
        source_type="ai_generated",
    )
    global_pending = _create(
        svc,
        db_session,
        admin,
        scope="global",
        org_id=None,
        subject_code="english",
        source_type="ocr_import",
    )
    _create(svc, db_session, other_admin)
    db_session.flush()

    staff_ids = {item.id for item in svc.list(db_session, viewer=staff)}
    admin_ids = {item.id for item in svc.list(db_session, viewer=admin)}
    pending_ids = {
        item.id for item in svc.list(db_session, viewer=admin, pending_only=True)
    }
    english_pending_ids = {
        item.id
        for item in svc.list(
            db_session,
            viewer=admin,
            status="pending_review",
            subject_code="english",
        )
    }

    assert staff_ids == {own_active.id, own_pending.id}
    assert admin_ids == {own_active.id, own_pending.id, global_pending.id}
    assert pending_ids == {own_pending.id, global_pending.id}
    assert english_pending_ids == {global_pending.id}


def test_list_supports_pagination(db_session):
    admin, _org = _admin(db_session)
    svc = QuestionBankService()
    created = [
        _create(svc, db_session, admin, stem=f"Question {index}")
        for index in range(3)
    ]
    db_session.flush()

    page1 = svc.list(db_session, viewer=admin, limit=2, offset=0)
    page2 = svc.list(db_session, viewer=admin, limit=2, offset=2)

    created_ids = {item.id for item in created}
    assert len(page1) == 2
    assert len(page2) == 1
    assert {item.id for item in page1}.issubset(created_ids)
    assert {item.id for item in page2}.issubset(created_ids)
    assert {item.id for item in page1}.isdisjoint({item.id for item in page2})
