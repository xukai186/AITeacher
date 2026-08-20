from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.auth.security import hash_password
from app.models import MediaAsset, UserRole
from app.services.media_assets import MAX_UPLOAD_BYTES
from app.services.question_ocr import QuestionOCRService, SegmentedOCRResult
from tests.factories import make_org, make_user

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"test-image"


def _staff_headers(client, db_session) -> tuple[dict[str, str], object]:
    org = make_org(db_session)
    staff = make_user(
        db_session,
        org,
        role=UserRole.org_staff,
        email="ocr-staff@example.com",
        password_hash=hash_password("pw1234"),
    )
    db_session.commit()
    login = client.post("/auth/login", json={"email": staff.email, "password": "pw1234"})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}, staff


def test_ocr_service_returns_structured_question_from_stub(db_session, monkeypatch, tmp_path):
    org = make_org(db_session)
    staff = make_user(db_session, org, role=UserRole.org_staff)
    image_path = tmp_path / "question.png"
    image_path.write_bytes(b"fake image")
    asset = MediaAsset(
        org_id=org.id,
        created_by=staff.id,
        content_type="image/png",
        storage_path=str(image_path),
    )
    db_session.add(asset)
    db_session.commit()

    monkeypatch.setattr(
        QuestionOCRService,
        "_extract",
        lambda self, path, content_type, policy: {
            "q_type": "single_choice",
            "stem": "Which answer is correct?",
            "choices": [{"key": "A", "text": "First"}],
            "answer_key": "A",
        },
    )

    result = QuestionOCRService().extract(db_session, org_id=org.id, asset_id=asset.id)

    assert result.stem == "Which answer is correct?"
    assert result.q_type == "single_choice"
    assert result.answer_key == "A"


def test_extract_segmented_returns_multiple_questions(db_session, monkeypatch, tmp_path):
    org = make_org(db_session)
    staff = make_user(db_session, org, role=UserRole.org_staff)
    image_path = tmp_path / "sheet.png"
    image_path.write_bytes(b"fake sheet")
    asset = MediaAsset(
        org_id=org.id,
        created_by=staff.id,
        content_type="image/png",
        storage_path=str(image_path),
    )
    db_session.add(asset)
    db_session.commit()

    monkeypatch.setattr(
        QuestionOCRService,
        "_extract_segmented",
        lambda self, path, content_type, policy: {
            "kind": "segmented",
            "questions": [
                {
                    "q_type": "single_choice",
                    "stem": "Q1",
                    "choices": [{"key": "A", "text": "1"}],
                    "answer_key": "A",
                },
                {
                    "q_type": "short_answer",
                    "stem": "Q2",
                    "choices": None,
                    "answer_key": "open",
                },
            ],
        },
    )

    result = QuestionOCRService().extract_segmented(
        db_session, org_id=org.id, asset_id=asset.id
    )
    assert result.kind == "segmented"
    assert len(result.questions) == 2
    assert result.questions[0].stem == "Q1"


def test_extract_segmented_raw_text_fallback(db_session, monkeypatch, tmp_path):
    org = make_org(db_session)
    staff = make_user(db_session, org, role=UserRole.org_staff)
    image_path = tmp_path / "sheet.png"
    image_path.write_bytes(b"fake sheet")
    asset = MediaAsset(
        org_id=org.id,
        created_by=staff.id,
        content_type="image/png",
        storage_path=str(image_path),
    )
    db_session.add(asset)
    db_session.commit()

    monkeypatch.setattr(
        QuestionOCRService,
        "_extract_segmented",
        lambda self, path, content_type, policy: {
            "kind": "raw_text_fallback",
            "raw_text": "1. First question ... 2. Second question ...",
        },
    )

    result = QuestionOCRService().extract_segmented(
        db_session, org_id=org.id, asset_id=asset.id
    )
    assert result.kind == "raw_text_fallback"
    assert "First question" in result.raw_text


def test_ocr_single_image_multi_question_segmented(client, db_session, monkeypatch, tmp_path):
    headers, staff = _staff_headers(client, db_session)
    monkeypatch.setattr("app.services.media_assets.MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(
        QuestionOCRService,
        "_extract_segmented",
        lambda self, path, content_type, policy: {
            "kind": "segmented",
            "questions": [
                {"q_type": "single_choice", "stem": "Q1", "choices": None, "answer_key": "A"},
                {"q_type": "short_answer", "stem": "Q2", "choices": None, "answer_key": "x"},
            ],
        },
    )
    uploaded = client.post(
        "/org/question-bank/upload-image",
        files={"file": ("sheet.png", PNG_BYTES, "image/png")},
        headers=headers,
    )
    asset_id = uploaded.json()["asset_id"]
    resp = client.post(
        "/org/question-bank/ocr",
        json={"mode": "single_image_multi_question", "asset_ids": [asset_id]},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "segmented"
    assert len(body["questions"]) == 2


def test_ocr_single_image_multi_question_raw_fallback(client, db_session, monkeypatch, tmp_path):
    headers, _ = _staff_headers(client, db_session)
    monkeypatch.setattr("app.services.media_assets.MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(
        QuestionOCRService,
        "_extract_segmented",
        lambda self, path, content_type, policy: {
            "kind": "raw_text_fallback",
            "raw_text": "raw sheet text",
        },
    )
    uploaded = client.post(
        "/org/question-bank/upload-image",
        files={"file": ("sheet.png", PNG_BYTES, "image/png")},
        headers=headers,
    )
    asset_id = uploaded.json()["asset_id"]
    resp = client.post(
        "/org/question-bank/ocr",
        json={"mode": "single_image_multi_question", "asset_ids": [asset_id]},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json() == {"mode": "raw_text_fallback", "raw_text": "raw sheet text"}


def test_legacy_asset_id_ocr_still_works(client, db_session, monkeypatch, tmp_path):
    headers, _ = _staff_headers(client, db_session)
    monkeypatch.setattr("app.services.media_assets.MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(
        QuestionOCRService,
        "_extract",
        lambda self, path, content_type, policy: {
            "q_type": "short_answer",
            "stem": "Explain the result.",
            "choices": None,
            "answer_key": "Because it follows.",
        },
    )
    uploaded = client.post(
        "/org/question-bank/upload-image",
        files={"file": ("question.png", PNG_BYTES, "image/png")},
        headers=headers,
    )
    asset_id = uploaded.json()["asset_id"]
    resp = client.post(
        "/org/question-bank/ocr",
        json={"asset_id": asset_id},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["stem"] == "Explain the result."
    assert "mode" not in resp.json()


def test_staff_uploads_image_then_extracts_question(
    client, db_session, monkeypatch, tmp_path
):
    headers, staff = _staff_headers(client, db_session)
    monkeypatch.setattr("app.services.media_assets.MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(
        QuestionOCRService,
        "_extract",
        lambda self, path, content_type, policy: {
            "q_type": "short_answer",
            "stem": "Explain the result.",
            "choices": None,
            "answer_key": "Because it follows.",
        },
    )

    uploaded = client.post(
        "/org/question-bank/upload-image",
        files={"file": ("question.png", PNG_BYTES, "image/png")},
        headers=headers,
    )

    assert uploaded.status_code == 201
    body = uploaded.json()
    asset = db_session.execute(
        select(MediaAsset).where(MediaAsset.id == body["asset_id"])
    ).scalar_one()
    assert asset.org_id == staff.org_id
    assert Path(asset.storage_path).read_bytes() == PNG_BYTES
    assert body["storage_key"] == f"{staff.org_id}/{asset.id}"
    assert not Path(body["storage_key"]).is_absolute()

    extracted = client.post(
        "/org/question-bank/ocr",
        json={"asset_id": body["asset_id"]},
        headers=headers,
    )
    assert extracted.status_code == 200
    assert extracted.json() == {
        "q_type": "short_answer",
        "stem": "Explain the result.",
        "choices": None,
        "answer_key": "Because it follows.",
    }


def test_upload_rejects_unsupported_spoofed_and_oversized_images(
    client, db_session, monkeypatch, tmp_path
):
    headers, _staff = _staff_headers(client, db_session)
    monkeypatch.setattr("app.services.media_assets.MEDIA_ROOT", tmp_path)

    unsupported = client.post(
        "/org/question-bank/upload-image",
        files={"file": ("question.gif", b"GIF89a", "image/gif")},
        headers=headers,
    )
    spoofed = client.post(
        "/org/question-bank/upload-image",
        files={"file": ("question.png", b"not a png", "image/png")},
        headers=headers,
    )
    oversized = client.post(
        "/org/question-bank/upload-image",
        files={
            "file": (
                "question.png",
                b"\x89PNG\r\n\x1a\n" + b"x" * MAX_UPLOAD_BYTES,
                "image/png",
            )
        },
        headers=headers,
    )

    assert unsupported.status_code == 415
    assert spoofed.status_code == 415
    assert oversized.status_code == 413
    assert list(tmp_path.rglob("*")) == []
