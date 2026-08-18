from __future__ import annotations

from app.auth.security import hash_password
from app.models import MediaAsset, SyllabusNode, UserRole
from tests.factories import make_org, make_user


def _seed_user(db, role: UserRole, *, email: str, password: str = "pw1234"):
    org = make_org(db)
    user = make_user(
        db,
        org,
        role=role,
        email=email,
        password_hash=hash_password(password),
    )
    db.commit()
    return user


def _headers(client, email: str, password: str = "pw1234") -> dict[str, str]:
    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _question_payload(**overrides):
    payload = {
        "scope": "org",
        "subject_code": "english",
        "knowledge_node_id": None,
        "q_type": "single_choice",
        "stem": "Which option is correct?",
        "choices": [{"key": "A", "text": "One"}, {"key": "B", "text": "Two"}],
        "answer_key": "A",
        "analysis_text": "A is correct.",
        "difficulty": 2,
        "source_type": "staff_manual",
    }
    payload.update(overrides)
    return payload


def _media_asset(db_session, actor):
    asset = MediaAsset(
        org_id=actor.org_id,
        created_by=actor.id,
        content_type="image/png",
        storage_path=f"/tmp/{actor.id}.png",
    )
    db_session.add(asset)
    db_session.commit()
    return asset


def test_admin_creates_lists_and_reviews_question_bank_items(client, db_session):
    admin = _seed_user(db_session, UserRole.org_admin, email="bank-admin@example.com")
    headers = _headers(client, admin.email)

    created = client.post(
        "/org/question-bank",
        json=_question_payload(),
        headers=headers,
    )
    assert created.status_code == 201
    assert created.json()["org_id"] == str(admin.org_id)
    assert created.json()["choices"] == [{"key": "A", "text": "One"}, {"key": "B", "text": "Two"}]
    assert created.json()["status"] == "active"

    pending = client.post(
        "/org/question-bank",
        json=_question_payload(
            stem="Explain a generated question",
            q_type="short_answer",
            choices=None,
            source_type="ai_generated",
        ),
        headers=headers,
    )
    assert pending.status_code == 201
    pending_id = pending.json()["id"]

    pending_list = client.get(
        "/org/question-bank?pending=1&subject_code=english",
        headers=headers,
    )
    assert pending_list.status_code == 200
    assert [row["id"] for row in pending_list.json()] == [pending_id]

    approved = client.post(
        f"/org/question-bank/{pending_id}/approve",
        headers=headers,
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "active"
    assert approved.json()["reviewed_by"] == str(admin.id)

    disabled = client.post(
        f"/org/question-bank/{pending_id}/disable",
        headers=headers,
    )
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "disabled"


def test_staff_can_enrich_create_and_reject_org_question(client, db_session):
    staff = _seed_user(db_session, UserRole.org_staff, email="bank-staff@example.com")
    headers = _headers(client, staff.email)

    enriched = client.post(
        "/org/question-bank/enrich",
        json={
            "stem": "Solve this math equation",
            "q_type": "short_answer",
            "choices": None,
            "answer_key": "2",
        },
        headers=headers,
    )
    assert enriched.status_code == 200
    assert enriched.json()["subject_code"] == "math"
    assert enriched.json()["difficulty"] == 3

    asset = _media_asset(db_session, staff)
    created = client.post(
        "/org/question-bank",
        json=_question_payload(
            stem="Question imported from an image",
            source_type="ocr_import",
            source_image_asset_id=str(asset.id),
        ),
        headers=headers,
    )
    assert created.status_code == 201
    assert created.json()["status"] == "pending_review"

    rejected = client.post(
        f"/org/question-bank/{created.json()['id']}/reject",
        headers=headers,
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"


def test_student_cannot_access_org_question_bank(client, db_session):
    student = _seed_user(db_session, UserRole.student, email="bank-student@example.com")
    response = client.get(
        "/org/question-bank",
        headers=_headers(client, student.email),
    )
    assert response.status_code == 403


def test_question_bank_list_supports_pagination(client, db_session):
    admin = _seed_user(db_session, UserRole.org_admin, email="bank-page-admin@example.com")
    headers = _headers(client, admin.email)

    for index in range(3):
        created = client.post(
            "/org/question-bank",
            json=_question_payload(stem=f"Paginated question {index}"),
            headers=headers,
        )
        assert created.status_code == 201

    page1 = client.get(
        "/org/question-bank?limit=2&offset=0",
        headers=headers,
    )
    assert page1.status_code == 200
    assert len(page1.json()) == 2

    page2 = client.get(
        "/org/question-bank?limit=2&offset=2",
        headers=headers,
    )
    assert page2.status_code == 200
    assert len(page2.json()) == 1

    page1_ids = {row["id"] for row in page1.json()}
    page2_ids = {row["id"] for row in page2.json()}
    assert page1_ids.isdisjoint(page2_ids)


def test_question_bank_list_resolves_knowledge_node_name(client, db_session):
    admin = _seed_user(db_session, UserRole.org_admin, email="bank-node-admin@example.com")
    parent = SyllabusNode(subject_code="math", name="极限", parent_id=None, weight=1)
    db_session.add(parent)
    db_session.flush()
    leaf = SyllabusNode(
        subject_code="math",
        name="导数",
        parent_id=parent.id,
        weight=1,
    )
    db_session.add(leaf)
    db_session.commit()

    headers = _headers(client, admin.email)
    created = client.post(
        "/org/question-bank",
        json=_question_payload(
            subject_code="math",
            knowledge_node_id=str(leaf.id),
            stem="求导数",
            q_type="short_answer",
            choices=None,
        ),
        headers=headers,
    )
    assert created.status_code == 201
    assert created.json()["knowledge_node_name"] == "极限 / 导数"

    listed = client.get("/org/question-bank?subject_code=math", headers=headers)
    assert listed.status_code == 200
    row = next(item for item in listed.json() if item["id"] == created.json()["id"])
    assert row["knowledge_node_name"] == "极限 / 导数"


def test_list_knowledge_nodes_returns_leaves(client, db_session):
    admin = _seed_user(db_session, UserRole.org_admin, email="nodes-admin@example.com")
    parent = SyllabusNode(subject_code="math", name="高数", parent_id=None, weight=1)
    db_session.add(parent)
    db_session.flush()
    leaf = SyllabusNode(subject_code="math", name="多元函数", parent_id=parent.id, weight=1)
    db_session.add(leaf)
    db_session.commit()
    headers = _headers(client, admin.email)

    resp = client.get("/org/question-bank/knowledge-nodes?subject_code=math", headers=headers)
    assert resp.status_code == 200
    row = next(r for r in resp.json() if r["id"] == str(leaf.id))
    assert row["name"] == "多元函数"
    assert row["parent_name"] == "高数"


def test_patch_question_bank_item(client, db_session):
    admin = _seed_user(db_session, UserRole.org_admin, email="patch-admin@example.com")
    asset = _media_asset(db_session, admin)
    headers = _headers(client, admin.email)
    created = client.post(
        "/org/question-bank",
        json=_question_payload(
            source_type="ocr_import",
            source_image_asset_id=str(asset.id),
        ),
        headers=headers,
    )
    assert created.status_code == 201
    item_id = created.json()["id"]

    patched = client.patch(
        f"/org/question-bank/{item_id}",
        json={"stem": "Patched stem", "difficulty": 4},
        headers=headers,
    )
    assert patched.status_code == 200
    assert patched.json()["stem"] == "Patched stem"
    assert patched.json()["difficulty"] == 4
    assert patched.json()["status"] == "pending_review"


def test_patch_active_question_returns_409(client, db_session):
    admin = _seed_user(db_session, UserRole.org_admin, email="patch-active@example.com")
    headers = _headers(client, admin.email)
    created = client.post("/org/question-bank", json=_question_payload(), headers=headers)
    item_id = created.json()["id"]

    resp = client.patch(
        f"/org/question-bank/{item_id}",
        json={"stem": "Cannot"},
        headers=headers,
    )
    assert resp.status_code == 409


def test_ocr_import_without_asset_returns_422(client, db_session):
    admin = _seed_user(db_session, UserRole.org_admin, email="ocr-no-asset@example.com")
    headers = _headers(client, admin.email)
    resp = client.post(
        "/org/question-bank",
        json=_question_payload(source_type="ocr_import"),
        headers=headers,
    )
    assert resp.status_code == 422


def test_ocr_import_with_org_asset_returns_201(client, db_session):
    admin = _seed_user(db_session, UserRole.org_admin, email="ocr-asset@example.com")
    asset = _media_asset(db_session, admin)
    headers = _headers(client, admin.email)
    resp = client.post(
        "/org/question-bank",
        json=_question_payload(
            source_type="ocr_import",
            source_image_asset_id=str(asset.id),
        ),
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "pending_review"
    assert resp.json()["source_image_asset_id"] == str(asset.id)


def test_delete_pending_question(client, db_session):
    admin = _seed_user(db_session, UserRole.org_admin, email="delete-admin@example.com")
    asset = _media_asset(db_session, admin)
    headers = _headers(client, admin.email)
    created = client.post(
        "/org/question-bank",
        json=_question_payload(
            source_type="ocr_import",
            source_image_asset_id=str(asset.id),
        ),
        headers=headers,
    )
    item_id = created.json()["id"]

    deleted = client.post(f"/org/question-bank/{item_id}/delete", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "deleted"

    listed = client.get("/org/question-bank", headers=headers)
    assert listed.status_code == 200
    assert item_id not in {row["id"] for row in listed.json()}


def test_delete_active_question_returns_409(client, db_session):
    admin = _seed_user(db_session, UserRole.org_admin, email="delete-active@example.com")
    headers = _headers(client, admin.email)
    created = client.post("/org/question-bank", json=_question_payload(), headers=headers)
    resp = client.post(
        f"/org/question-bank/{created.json()['id']}/delete",
        headers=headers,
    )
    assert resp.status_code == 409
