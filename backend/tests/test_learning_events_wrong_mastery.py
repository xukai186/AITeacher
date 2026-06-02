from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.auth.security import hash_password
from app.models import LearningEvent, WrongBookItem, UserRole
from app.services.wrong_book_mastery import WrongBookMasteryService
from tests.factories import make_org, make_user


def _wrong_item(db, student):
    item = WrongBookItem(
        student_user_id=student.id,
        subject_code="english",
        source_type="self_test",
        question_snapshot_json={
            "q_type": "single_choice",
            "stem": "test",
        },
        answer_snapshot_json={"content": "B"},
        correct_snapshot_json={"answer_key": "A"},
        status="active",
    )
    db.add(item)
    db.flush()
    return item


def test_mastery_requires_two_correct_with_gap(db_session):
    org = make_org(db_session)
    student = make_user(
        db_session,
        org,
        role=UserRole.student,
        email="mastery@demo.example",
        password_hash=hash_password("pw"),
    )
    item = _wrong_item(db_session, student)
    svc = WrongBookMasteryService()
    t0 = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)

    r1 = svc.practice(db_session, item=item, content="A", now=t0)
    assert r1.is_correct and r1.consecutive_correct_count == 1 and not r1.mastered

    r2 = svc.practice(db_session, item=item, content="A", now=t0 + timedelta(hours=12))
    assert r2.is_correct and r2.consecutive_correct_count == 1 and not r2.mastered

    r3 = svc.practice(db_session, item=item, content="A", now=t0 + timedelta(days=1))
    assert r3.mastered and item.status == "mastered"

    events = db_session.execute(
        select(LearningEvent.event_type).where(
            LearningEvent.student_user_id == student.id,
            LearningEvent.ref_id == item.id,
        )
    ).scalars().all()
    assert "wrong_mastered" in events


def test_wrong_practice_resets_streak(db_session):
    org = make_org(db_session)
    student = make_user(
        db_session,
        org,
        role=UserRole.student,
        email="reset@demo.example",
        password_hash=hash_password("pw"),
    )
    item = _wrong_item(db_session, student)
    svc = WrongBookMasteryService()
    t0 = datetime(2026, 6, 1, tzinfo=timezone.utc)
    svc.practice(db_session, item=item, content="A", now=t0)
    svc.practice(db_session, item=item, content="B", now=t0 + timedelta(hours=1))
    assert item.consecutive_correct_count == 0


def test_practice_and_archive_api(client, db_session):
    org = make_org(db_session)
    student = make_user(
        db_session,
        org,
        role=UserRole.student,
        email="api-wb@demo.example",
        password_hash=hash_password("pw"),
    )
    item = _wrong_item(db_session, student)
    db_session.commit()

    token = client.post(
        "/auth/login", json={"email": "api-wb@demo.example", "password": "pw"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    t0 = datetime(2026, 6, 1, tzinfo=timezone.utc)
    WrongBookMasteryService().practice(db_session, item=item, content="A", now=t0)
    WrongBookMasteryService().practice(
        db_session, item=item, content="A", now=t0 + timedelta(days=2)
    )
    db_session.commit()

    listed = client.get("/student/wrong-book?status=mastered", headers=headers)
    assert listed.status_code == 200
    assert any(row["id"] == str(item.id) for row in listed.json())

    arch = client.post(f"/student/wrong-book/{item.id}/archive", headers=headers)
    assert arch.status_code == 200
    assert arch.json()["status"] == "archived"
