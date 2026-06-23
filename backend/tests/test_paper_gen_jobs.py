from sqlalchemy import select

from app.auth.security import hash_password
from app.models import ModelPolicy, PaperGenJob, PlacementPaper, PlacementQuestion, StudentProfile, StudentSubject, UserRole
from app.seed_syllabus import seed_minimal_syllabus
from app.services.placement import PlacementService
from app.services.paper_gen_jobs import STALE_RUNNING_SECONDS, PaperGenJobRunner, PaperGenJobService
from tests.factories import make_org, make_user
from tests.paper_gen_job_helpers import finish_paper_gen_jobs

def _seed_student(db):
    org = make_org(db)
    student = make_user(
        db,
        org,
        role=UserRole.student,
        email="pg-job@demo.example",
        password_hash=hash_password("pw"),
    )
    seed_minimal_syllabus(db)
    db.add(StudentProfile(user_id=student.id, exam_year=2027))
    db.add(StudentSubject(student_user_id=student.id, subject_code="math", enabled=True))
    db.add(
        ModelPolicy(
            org_id=org.id,
            scene="paper_gen",
            provider="mock",
            model="mock-v1",
            params={},
        )
    )
    db.commit()
    return student


def test_placement_start_enqueues_and_runner_generates_questions(db_session):
    student = _seed_student(db_session)

    out = PlacementService.start(db_session, student.id, subject_code="math")
    assert out.gen_job_id is not None

    job = db_session.get(PaperGenJob, out.gen_job_id)
    assert job is not None
    assert job.status == "pending"

    finish_paper_gen_jobs(db_session)
    db_session.commit()

    db_session.refresh(job)
    assert job.status == "succeeded"

    paper = db_session.get(PlacementPaper, out.subjects[0].paper_id)
    assert paper is not None
    assert paper.status == "ready"
    questions = (
        db_session.execute(
            select(PlacementQuestion).where(PlacementQuestion.paper_id == paper.id)
        )
        .scalars()
        .all()
    )
    assert len(questions) == 22


def test_paper_gen_job_get_endpoint_runs_pending(client, db_session):
    student = _seed_student(db_session)
    token = client.post("/auth/login", json={"email": "pg-job@demo.example", "password": "pw"}).json()[
        "access_token"
    ]

    out = PlacementService.start(db_session, student.id, subject_code="math")
    assert out.gen_job_id is not None
    db_session.commit()

    resp = client.get(
        f"/student/paper-gen-jobs/{out.gen_job_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] in ("pending", "running")

    finish_paper_gen_jobs(db_session)
    db_session.commit()

    resp = client.get(
        f"/student/paper-gen-jobs/{out.gen_job_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "succeeded"
    assert body["progress"]["done"] == 22


def test_run_pending_reclaims_stale_running_job(db_session):
    from datetime import datetime, timedelta, timezone

    student = _seed_student(db_session)
    out = PlacementService.start(db_session, student.id, subject_code="math")
    assert out.gen_job_id is not None

    job = db_session.get(PaperGenJob, out.gen_job_id)
    assert job is not None
    job.status = "running"
    job.locked_at = datetime.now(timezone.utc) - timedelta(seconds=STALE_RUNNING_SECONDS + 1)
    db_session.commit()

    ran = PaperGenJobRunner().run_pending(db_session, limit=1, job_id=out.gen_job_id)
    db_session.commit()

    assert ran == 1
    db_session.refresh(job)
    assert job.status == "succeeded"


def test_enqueue_resets_succeeded_job_for_regeneration(db_session):
    student = _seed_student(db_session)

    out = PlacementService.start(db_session, student.id, subject_code="math")
    assert out.gen_job_id is not None
    finish_paper_gen_jobs(db_session)
    db_session.commit()

    job = db_session.get(PaperGenJob, out.gen_job_id)
    assert job is not None
    assert job.status == "succeeded"

    regen = PaperGenJobService().enqueue(
        db_session,
        student_user_id=student.id,
        subject_code="math",
        purpose="placement",
        paper_id=out.subjects[0].paper_id,
    )
    db_session.commit()

    assert regen.job_id == job.id
    db_session.refresh(job)
    assert job.status == "pending"
    assert job.attempts == 0


def test_placement_get_paper_includes_gen_job_id_while_generating(db_session):
    student = _seed_student(db_session)

    out = PlacementService.start(db_session, student.id, subject_code="math")
    assert out.gen_job_id is not None

    paper = PlacementService.get_paper(
        db_session, student.id, out.subjects[0].paper_id
    )
    assert paper.status == "generating"
    assert paper.gen_job_id == out.gen_job_id
    assert paper.questions == []
