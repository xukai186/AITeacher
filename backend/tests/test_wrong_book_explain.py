import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from sqlalchemy import func, select

from app.auth.security import hash_password
from app.models import ChatMessage, StudentProfile, StudentSubject, UserRole, WrongBookItem
from app.services.chat_tool_loop import ChatToolLoop, ChatTurnResult
from app.services.wrong_book_explain import WrongBookExplainService
from tests.factories import make_org, make_user


def _seed_student(db):
    org = make_org(db)
    student = make_user(
        db,
        org,
        role=UserRole.student,
        email="student@demo.example",
        password_hash=hash_password("pw"),
    )
    db.add(StudentProfile(user_id=student.id, exam_year=2027))
    db.add(StudentSubject(student_user_id=student.id, subject_code="english"))
    db.commit()
    return student


def _token(client):
    return client.post("/auth/login", json={"email": "student@demo.example", "password": "pw"}).json()[
        "access_token"
    ]


def _seed_item(db, student, *, explanation_text=None):
    item = WrongBookItem(
        student_user_id=student.id,
        subject_code="english",
        source_type="self_test",
        question_snapshot_json={"stem": "Pick the word"},
        answer_snapshot_json={"content": "wrong"},
        correct_snapshot_json={"answer_key": "right"},
        status="active",
        explanation_text=explanation_text,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def test_explain_generates_and_caches(client, db_session):
    student = _seed_student(db_session)
    item = _seed_item(db_session, student)
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post(f"/student/wrong-book/{item.id}/explain", json={}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["from_cache"] is False
    assert body["explanation_text"]
    assert body["explanation_created_at"] is not None

    n_msgs = db_session.execute(select(func.count()).select_from(ChatMessage)).scalar()
    assert n_msgs == 0


def test_explain_second_request_uses_cache_without_tool_loop(client, db_session, monkeypatch):
    student = _seed_student(db_session)
    item = _seed_item(db_session, student)
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}

    first = client.post(f"/student/wrong-book/{item.id}/explain", json={}, headers=headers)
    assert first.status_code == 200
    cached_text = first.json()["explanation_text"]

    def _fail_if_called(*_args, **_kwargs):
        raise AssertionError("ChatToolLoop.run must not be called on cache hit")

    monkeypatch.setattr(ChatToolLoop, "run", _fail_if_called)

    second = client.post(f"/student/wrong-book/{item.id}/explain", json={"regenerate": False}, headers=headers)
    assert second.status_code == 200
    body = second.json()
    assert body["from_cache"] is True
    assert body["explanation_text"] == cached_text


def test_explain_regenerate_calls_model_and_overwrites(client, db_session, monkeypatch):
    student = _seed_student(db_session)
    item = _seed_item(db_session, student, explanation_text="old")
    item.explanation_created_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
    db_session.commit()

    calls = {"n": 0}

    def _fake_run(*_args, **_kwargs):
        calls["n"] += 1
        return ChatTurnResult(assistant_message=f"new explanation #{calls['n']}")

    monkeypatch.setattr(ChatToolLoop, "run", _fake_run)

    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.post(
        f"/student/wrong-book/{item.id}/explain",
        json={"regenerate": True},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["from_cache"] is False
    assert body["explanation_text"] == "new explanation #1"
    assert body["explanation_text"] != "old"
    assert calls["n"] == 1


def test_explain_other_student_item_404(client, db_session):
    owner = _seed_student(db_session)
    item = _seed_item(db_session, owner)

    org2 = make_org(db_session)
    other = make_user(
        db_session,
        org2,
        role=UserRole.student,
        email="other@demo.example",
        password_hash=hash_password("pw2"),
    )
    db_session.add(StudentProfile(user_id=other.id, exam_year=2027))
    db_session.commit()

    token_other = client.post(
        "/auth/login", json={"email": "other@demo.example", "password": "pw2"}
    ).json()["access_token"]

    resp = client.post(
        f"/student/wrong-book/{item.id}/explain",
        json={},
        headers={"Authorization": f"Bearer {token_other}"},
    )
    assert resp.status_code == 404


def test_explain_service_unit_cache_hit(db_session):
    student = _seed_student(db_session)
    item = _seed_item(db_session, student, explanation_text="stored")
    tool_loop = MagicMock(spec=ChatToolLoop)
    svc = WrongBookExplainService(tool_loop=tool_loop)

    result = svc.explain(db_session, item=item, student_user_id=student.id, regenerate=False)

    assert result.from_cache is True
    assert result.explanation_text == "stored"
    tool_loop.run.assert_not_called()
