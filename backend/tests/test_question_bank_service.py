import uuid

import pytest
from fastapi import HTTPException

from app.models import MediaAsset, QuestionBankItem, SyllabusNode, UserRole
from app.schemas.question_bank import QuestionBankCreate
from app.services.question_bank import QuestionBankService
from tests.factories import make_org, make_user


def _admin(db_session):
    org = make_org(db_session)
    return make_user(db_session, org, UserRole.org_admin), org


def _staff(db_session, org):
    return make_user(db_session, org, UserRole.org_staff)


def _media_asset(db_session, actor, org_id=None):
    asset = MediaAsset(
        org_id=org_id or actor.org_id,
        created_by=actor.id,
        content_type="image/png",
        storage_path=f"/tmp/{uuid.uuid4()}.png",
    )
    db_session.add(asset)
    db_session.flush()
    return asset


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
    if (
        values.get("source_type") == "ocr_import"
        and "source_image_asset_id" not in overrides
    ):
        values["source_image_asset_id"] = _media_asset(db_session, actor).id
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


def test_ocr_import_requires_source_image_asset(db_session):
    admin, _ = _admin(db_session)
    with pytest.raises(HTTPException) as exc:
        _create(
            QuestionBankService(),
            db_session,
            admin,
            source_type="ocr_import",
            source_image_asset_id=None,
        )
    assert exc.value.status_code == 422


def test_ocr_import_rejects_foreign_org_asset(db_session):
    admin, _ = _admin(db_session)
    other = make_org(db_session, "Other")
    foreign_admin = make_user(db_session, other, UserRole.org_admin)
    asset = _media_asset(db_session, foreign_admin, org_id=other.id)
    with pytest.raises(HTTPException) as exc:
        _create(
            QuestionBankService(),
            db_session,
            admin,
            source_type="ocr_import",
            source_image_asset_id=asset.id,
        )
    assert exc.value.status_code == 422


def test_ocr_import_accepts_actor_org_asset(db_session):
    admin, _ = _admin(db_session)
    asset = _media_asset(db_session, admin)
    item = _create(
        QuestionBankService(),
        db_session,
        admin,
        source_type="ocr_import",
        source_image_asset_id=asset.id,
    )
    assert item.status == "pending_review"
    assert item.source_image_asset_id == asset.id


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


def test_list_scope_filter_for_admin_and_staff(db_session):
    admin, org = _admin(db_session)
    staff = _staff(db_session, org)
    svc = QuestionBankService()
    own = _create(svc, db_session, admin, stem="Org only")
    global_item = _create(
        svc,
        db_session,
        admin,
        scope="global",
        org_id=None,
        stem="Global only",
        source_type="admin_manual",
    )
    db_session.flush()

    admin_all = {i.id for i in svc.list(db_session, viewer=admin)}
    admin_org = {i.id for i in svc.list(db_session, viewer=admin, scope="org")}
    admin_global = {i.id for i in svc.list(db_session, viewer=admin, scope="global")}
    staff_global = list(svc.list(db_session, viewer=staff, scope="global"))
    staff_org = {i.id for i in svc.list(db_session, viewer=staff, scope="org")}

    assert admin_all == {own.id, global_item.id}
    assert admin_org == {own.id}
    assert admin_global == {global_item.id}
    assert staff_global == []
    assert staff_org == {own.id}


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


def test_list_leaf_knowledge_nodes_returns_only_leaves(db_session):
    parent = SyllabusNode(subject_code="math", name="高数", parent_id=None, weight=1)
    db_session.add(parent)
    db_session.flush()
    leaf = SyllabusNode(subject_code="math", name="多元函数", parent_id=parent.id, weight=1)
    mid = SyllabusNode(subject_code="math", name="章节", parent_id=None, weight=1)
    db_session.add_all([leaf, mid])
    db_session.flush()
    child = SyllabusNode(subject_code="math", name="小节", parent_id=mid.id, weight=1)
    db_session.add(child)
    db_session.flush()

    svc = QuestionBankService()
    leaves = svc.list_leaf_knowledge_nodes(db_session, subject_code="math")
    ids = {n.id for n in leaves}
    assert leaf.id in ids
    assert child.id in ids
    assert mid.id not in ids
    assert parent.id not in ids


def test_update_pending_review_keeps_status(db_session):
    admin, org = _admin(db_session)
    svc = QuestionBankService()
    item = _create(svc, db_session, admin, source_type="ocr_import")
    db_session.flush()

    updated = svc.update(
        db_session,
        actor=admin,
        item_id=item.id,
        stem="Updated stem",
    )
    assert updated.status == "pending_review"
    assert updated.stem == "Updated stem"


def test_update_rejected_returns_to_pending_review(db_session):
    admin, org = _admin(db_session)
    svc = QuestionBankService()
    item = _create(svc, db_session, admin, source_type="ocr_import")
    svc.reject(db_session, actor=admin, item_id=item.id)
    db_session.flush()
    assert item.reviewed_by is not None

    updated = svc.update(db_session, actor=admin, item_id=item.id, stem="Fix it")
    assert updated.status == "pending_review"
    assert updated.reviewed_by is None
    assert updated.reviewed_at is None


def test_update_active_is_rejected(db_session):
    admin, org = _admin(db_session)
    svc = QuestionBankService()
    item = _create(svc, db_session, admin)
    db_session.flush()

    with pytest.raises(HTTPException) as exc:
        svc.update(db_session, actor=admin, item_id=item.id, stem="Nope")
    assert exc.value.status_code == 409


def test_delete_pending_review_sets_deleted(db_session):
    admin, _ = _admin(db_session)
    svc = QuestionBankService()
    item = _create(svc, db_session, admin, source_type="ocr_import")
    deleted = svc.delete(db_session, actor=admin, item_id=item.id)
    assert deleted.status == "deleted"


def test_delete_active_is_rejected(db_session):
    admin, _ = _admin(db_session)
    svc = QuestionBankService()
    item = _create(svc, db_session, admin)
    with pytest.raises(HTTPException) as exc:
        svc.delete(db_session, actor=admin, item_id=item.id)
    assert exc.value.status_code == 409


def test_delete_already_deleted_is_rejected(db_session):
    admin, _ = _admin(db_session)
    svc = QuestionBankService()
    item = _create(svc, db_session, admin, source_type="ocr_import")
    svc.delete(db_session, actor=admin, item_id=item.id)
    with pytest.raises(HTTPException) as exc:
        svc.delete(db_session, actor=admin, item_id=item.id)
    assert exc.value.status_code == 409


def test_list_excludes_deleted_even_when_status_filter_is_deleted(db_session):
    admin, _ = _admin(db_session)
    svc = QuestionBankService()
    live = _create(svc, db_session, admin, stem="Keep me")
    doomed = _create(svc, db_session, admin, source_type="ocr_import", stem="Drop me")
    svc.delete(db_session, actor=admin, item_id=doomed.id)
    db_session.flush()

    ids = {item.id for item in svc.list(db_session, viewer=admin)}
    assert live.id in ids
    assert doomed.id not in ids
    assert svc.list(db_session, viewer=admin, status="deleted") == []


def test_dedupe_ignores_deleted_so_stem_can_be_recreated(db_session):
    admin, org = _admin(db_session)
    svc = QuestionBankService()
    original = _create(svc, db_session, admin, source_type="ocr_import", stem="Same stem")
    svc.delete(db_session, actor=admin, item_id=original.id)
    db_session.flush()

    assert (
        svc.find_exact_duplicate(
            db_session, scope="org", org_id=org.id, q_type="single_choice", stem="Same stem"
        )
        is None
    )
    recreated = _create(svc, db_session, admin, stem="Same stem")
    assert recreated.status == "active"


def test_unique_index_blocks_duplicate_insert(db_session):
    admin, org = _admin(db_session)
    svc = QuestionBankService()
    stem = "Index duplicate stem"
    _create(svc, db_session, admin, stem=stem)

    duplicate = QuestionBankItem(
        scope="org",
        org_id=org.id,
        subject_code="english",
        knowledge_node_id=None,
        q_type="single_choice",
        stem=stem,
        choices_json=[{"key": "A", "text": "1"}],
        answer_key="A",
        source_type="admin_manual",
        status="active",
        created_by=admin.id,
    )
    db_session.add(duplicate)

    with pytest.raises(HTTPException) as exc:
        QuestionBankService._flush_or_raise_duplicate(db_session)
    assert exc.value.status_code == 409
    assert exc.value.detail == "exact question bank duplicate"


def test_update_rejected_to_pending_conflicts_when_active_exists(db_session):
    admin, _ = _admin(db_session)
    svc = QuestionBankService()
    stem = "Conflict stem"
    pending = _create(
        svc,
        db_session,
        admin,
        stem=stem,
        source_type="ai_generated",
    )
    svc.reject(db_session, actor=admin, item_id=pending.id)
    _create(
        svc,
        db_session,
        admin,
        stem=stem,
        source_type="admin_manual",
        allow_inactive_duplicate=True,
    )

    with pytest.raises(HTTPException) as exc:
        svc.update(db_session, actor=admin, item_id=pending.id, analysis_text="retry")
    assert exc.value.status_code == 409


def test_update_stem_conflicts_with_existing_active(db_session):
    admin, _ = _admin(db_session)
    svc = QuestionBankService()
    _create(svc, db_session, admin, stem="Taken stem", source_type="admin_manual")
    pending = _create(
        svc,
        db_session,
        admin,
        stem="Other stem",
        source_type="ai_generated",
    )

    with pytest.raises(HTTPException) as exc:
        svc.update(db_session, actor=admin, item_id=pending.id, stem="Taken stem")
    assert exc.value.status_code == 409


def test_global_duplicate_rejected(db_session):
    admin, _ = _admin(db_session)
    svc = QuestionBankService()
    stem = "Global duplicate stem"
    _create(
        svc,
        db_session,
        admin,
        scope="global",
        org_id=None,
        stem=stem,
        source_type="admin_manual",
    )

    with pytest.raises(HTTPException) as exc:
        _create(
            svc,
            db_session,
            admin,
            scope="global",
            org_id=None,
            stem=stem,
            source_type="admin_manual",
        )
    assert exc.value.status_code == 409
