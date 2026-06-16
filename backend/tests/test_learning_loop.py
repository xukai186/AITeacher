from datetime import date, timedelta

from sqlalchemy import select

from app.auth.security import hash_password
from app.models import (
    DailyTask,
    MasterySnapshot,
    PlanReviewJob,
    SelfTestPaper,
    StudentProfile,
    StudentSubject,
    UserRole,
)
from app.services.agent_tools import default_tool_registry
from app.services.completion_rate_review import CompletionRateReviewService
from app.services.mastery import MasteryService
from app.services.planning import PlanningService
from app.services.self_test import SelfTestService
from app.services.self_test_eligibility import SelfTestEligibilityService
from app.services.wrong_book_followup import WrongBookFollowUpService
from tests.factories import make_org, make_user
from tests.paper_gen_job_helpers import finish_paper_gen_jobs, generate_self_test_and_wait


def _student_with_placement(db_session):
    org = make_org(db_session)
    student = make_user(
        db_session,
        org,
        role=UserRole.student,
        email="loop@demo.example",
        password_hash=hash_password("pw"),
    )
    db_session.add(StudentProfile(user_id=student.id, exam_year=2027))
    db_session.add(StudentSubject(student_user_id=student.id, subject_code="english"))
    db_session.commit()
    PlanningService().create_initial_plans(db_session, student_user_id=student.id)
    db_session.add(
        MasterySnapshot(
            student_user_id=student.id,
            subject_code="english",
            version=1,
            mastery_json={"00000000-0000-0000-0000-000000000001": 3},
        )
    )
    db_session.commit()
    return student


def test_self_test_submit_updates_mastery_and_schedules_review_tasks(client, db_session):
    student = _student_with_placement(db_session)
    token = client.post(
        "/auth/login", json={"email": "loop@demo.example", "password": "pw"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert SelfTestEligibilityService().check(
        db_session, student_user_id=student.id, subject_code="english"
    ).allowed

    gen = generate_self_test_and_wait(client, token, db_session=db_session)
    paper_id = gen["id"]
    paper = client.get(f"/student/self-tests/{paper_id}", headers=headers).json()
    answers = [{"question_id": q["id"], "content": "Z"} for q in paper["questions"]]
    client.post(
        f"/student/self-tests/{paper_id}/submit",
        json={"answers": answers},
        headers=headers,
    )

    snap = db_session.execute(
        select(MasterySnapshot).where(
            MasterySnapshot.student_user_id == student.id,
            MasterySnapshot.subject_code == "english",
        )
    ).scalar_one()
    assert snap.mastery_json

    tomorrow = date.today() + timedelta(days=1)
    day3 = date.today() + timedelta(days=3)
    review_tasks = db_session.execute(
        select(DailyTask).where(
            DailyTask.student_user_id == student.id,
            DailyTask.type == "review_wrong",
            DailyTask.date >= tomorrow,
            DailyTask.date <= day3,
        )
    ).scalars().all()
    assert len(review_tasks) >= 1
    assert all(t.payload_json.get("source") == "self_test_graded" for t in review_tasks)


def test_generate_paper_tool_respects_eligibility(db_session):
    student = _student_with_placement(db_session)
    paper, _ = SelfTestService.generate(db_session, student.id, "english")
    finish_paper_gen_jobs(db_session)
    db_session.commit()
    out = default_tool_registry.call(
        db_session,
        "generate_paper",
        student_user_id=student.id,
        subject_code="english",
    )
    assert out["ok"] is False
    assert out["reasons"]


def test_low_completion_rate_enqueues_plan_review(db_session):
    student = _student_with_placement(db_session)
    today = date.today()
    for offset in range(3):
        d = today - timedelta(days=offset)
        db_session.add(
            DailyTask(
                student_user_id=student.id,
                date=d,
                subject_code="english",
                type="study",
                status="pending",
                est_minutes=30,
                title="学习",
            )
        )
    db_session.commit()

    ok = CompletionRateReviewService().maybe_enqueue_for_student_subject(
        db_session,
        student_user_id=student.id,
        subject_code="english",
    )
    assert ok is True
    job = db_session.execute(
        select(PlanReviewJob).where(
            PlanReviewJob.student_user_id == student.id,
            PlanReviewJob.trigger == "low_completion_rate",
        )
    ).scalar_one()
    assert job.subject_code == "english"


def test_wrong_book_followup_idempotent(db_session):
    student = _student_with_placement(db_session)
    paper = SelfTestPaper(student_user_id=student.id, subject_code="english", status="ready")
    db_session.add(paper)
    db_session.flush()
    from app.models import SelfTestSubmission

    sub = SelfTestSubmission(
        paper_id=paper.id, student_user_id=student.id, status="submitted"
    )
    db_session.add(sub)
    db_session.flush()
    svc = WrongBookFollowUpService()
    assert svc.schedule_after_self_test(
        db_session,
        student_user_id=student.id,
        subject_code="english",
        submission_id=sub.id,
    ) == 0

