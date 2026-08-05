from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.auth.security import hash_password
from app.models import MediaAsset, UserRole
from app.services.question_ocr import QuestionOCRService
from tests.factories import make_org, make_user


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
        files={"file": ("question.png", b"image bytes", "image/png")},
        headers=headers,
    )

    assert uploaded.status_code == 201
    body = uploaded.json()
    asset = db_session.execute(
        select(MediaAsset).where(MediaAsset.id == body["asset_id"])
    ).scalar_one()
    assert asset.org_id == staff.org_id
    assert Path(asset.storage_path).read_bytes() == b"image bytes"
    assert body["url_or_path"] == asset.storage_path

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
