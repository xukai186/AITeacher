import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.auth.security import hash_password
from app.models import DailyTask, MasterPlan, MasterPlanVersion, MasterySnapshot, PlacementPaper, PlacementQuestion, PlacementResult, StudentExamProfile, StudentProfile, StudentSubject, StudyRoadmap, SubjectPlan, SubjectPlanVersion, UserRole, WrongBookItem
from app.seed_exam_majors import seed_exam_majors
from tests.factories import make_org, make_user
from tests.paper_gen_job_helpers import start_placement_and_wait


def _placement_answer_content(q: PlacementQuestion) -> str:
    if q.q_type in ("short_answer", "essay"):
        return "参考作答要点"
    return q.answer_key or "A"


def _seed_student(db, *, complete_exam_profile: bool = True):
    seed_exam_majors(db)
    org = make_org(db)
    student = make_user(
        db,
        org,
        role=UserRole.student,
        email=f"placement-flow-{uuid.uuid4().hex[:8]}@demo.example",
        password_hash=hash_password("pw"),
    )
    db.add(StudentProfile(user_id=student.id, exam_year=2027))
    db.add(StudentSubject(student_user_id=student.id, subject_code="english", enabled=True))
    if complete_exam_profile:
        db.add(
            StudentExamProfile(
                user_id=student.id,
                major_category_code="academic_master",
                major_code="cs_academic",
                subject_codes=["english"],
                profile_completed_at=datetime.now(timezone.utc),
            )
        )
    db.commit()
    return student


def _token(client, email: str):
    return client.post(
        "/auth/login",
        json={"email": email, "password": "pw"},
    ).json()["access_token"]


def test_placement_start_requires_complete_exam_profile(client, db_session):
    student = _seed_student(db_session, complete_exam_profile=False)
    token = _token(client, student.email)

    start = client.post(
        "/student/placement/start",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert start.status_code == 400
    assert "报考档案" in start.json()["detail"]


def test_student_can_start_placement_and_get_paper(client, db_session):
    student = _seed_student(db_session)
    token = _token(client, student.email)
    start_placement_and_wait(client, token, db_session=db_session)

    papers = (
        db_session.execute(
            select(PlacementPaper).where(PlacementPaper.student_user_id == student.id)
        )
        .scalars()
        .all()
    )
    assert len(papers) == 1


def test_student_can_submit_placement_and_get_result(client, db_session):
    student = _seed_student(db_session)
    token = _token(client, student.email)
    start_placement_and_wait(client, token, db_session=db_session)

    paper_id = client.get("/student/placement", headers={"Authorization": f"Bearer {token}"}).json()[0]["id"]
    paper = client.get(f"/student/placement/{paper_id}", headers={"Authorization": f"Bearer {token}"}).json()

    questions = (
        db_session.execute(select(PlacementQuestion).where(PlacementQuestion.paper_id == paper_id))
        .scalars()
        .all()
    )
    assert questions

    payload = {
        "answers": [
            {"question_id": str(q.id), "content": _placement_answer_content(q)}
            for q in questions
        ]
    }
    submit = client.post(
        f"/student/placement/{paper_id}/submit",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert submit.status_code == 200
    out = submit.json()
    assert out["paper_id"] == paper_id
    assert out["total_score"] > 0
    assert db_session.query(PlacementResult).count() >= 1
    assert out["all_placement_complete"] is True
    assert out["roadmap_job_id"] is not None
    assert (
        db_session.query(MasterySnapshot)
        .filter(MasterySnapshot.student_user_id == student.id)
        .count()
        == 1
    )
    roadmap = (
        db_session.query(StudyRoadmap).filter(StudyRoadmap.student_user_id == student.id).one_or_none()
    )
    assert roadmap is not None
    assert roadmap.pending_version_id is not None
    assert (
        db_session.query(MasterPlan).filter(MasterPlan.student_user_id == student.id).count()
        == 0
    )


def test_placement_submit_with_existing_mastery_snapshot(client, db_session):
    """Orphan mastery snapshot (e.g. after question regen) must not block submit."""
    student = _seed_student(db_session)
    token = _token(client, student.email)
    start = start_placement_and_wait(
        client,
        token,
        {"subject_code": "english"},
        db_session=db_session,
    )
    paper_id = start["subjects"][0]["paper_id"]

    from app.models import MasterySnapshot

    db_session.add(
        MasterySnapshot(
            student_user_id=student.id,
            subject_code="english",
            version=1,
            mastery_json={"old": 1},
        )
    )
    db_session.commit()

    questions = (
        db_session.execute(select(PlacementQuestion).where(PlacementQuestion.paper_id == paper_id))
        .scalars()
        .all()
    )
    submit = client.post(
        f"/student/placement/{paper_id}/submit",
        json={
            "answers": [
                {"question_id": str(q.id), "content": _placement_answer_content(q)}
                for q in questions
            ]
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert submit.status_code == 200
    snap = db_session.execute(
        select(MasterySnapshot).where(
            MasterySnapshot.student_user_id == student.id,
            MasterySnapshot.subject_code == "english",
        )
    ).scalar_one()
    assert "old" not in snap.mastery_json


def test_wrong_book_ingested_after_placement_submit(client, db_session):
    student = _seed_student(db_session)
    token = _token(client, student.email)
    start_placement_and_wait(client, token, db_session=db_session)

    paper_id = client.get("/student/placement", headers={"Authorization": f"Bearer {token}"}).json()[0]["id"]

    questions = (
        db_session.execute(select(PlacementQuestion).where(PlacementQuestion.paper_id == paper_id))
        .scalars()
        .all()
    )
    assert questions

    payload = {"answers": [{"question_id": str(q.id), "content": "Z"} for q in questions]}
    submit = client.post(
        f"/student/placement/{paper_id}/submit",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert submit.status_code == 200

    items = db_session.execute(select(WrongBookItem).where(WrongBookItem.source_type == "placement")).scalars().all()
    assert len(items) > 0
