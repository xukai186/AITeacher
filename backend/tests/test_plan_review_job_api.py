from datetime import date, timedelta

from app.auth.security import hash_password
from app.models import PlanReviewJob, StudentProfile, StudentSubject, UserRole
from app.services.plan_review_jobs import PlanReviewJobRunner
from app.services.planning import PlanningService
from tests.factories import make_org, make_user


def _seed(client, db):
    org = make_org(db)
    student = make_user(
        db,
        org,
        role=UserRole.student,
        email="job-api@demo.example",
        password_hash=hash_password("pw"),
    )
    db.add(StudentProfile(user_id=student.id, exam_year=2027))
    db.add(StudentSubject(student_user_id=student.id, subject_code="english"))
    db.commit()
    PlanningService().create_initial_plans(db, student_user_id=student.id)
    db.commit()
    token = client.post(
        "/auth/login", json={"email": "job-api@demo.example", "password": "pw"}
    ).json()["access_token"]
    return student, token


def test_apply_recommendations_enqueues_and_polls(client, db_session):
    student, token = _seed(client, db_session)
    tomorrow = date.today() + timedelta(days=1)

    resp = client.post(
        "/student/agent/apply-recommendations",
        params={"subject_code": "english", "target_date": tomorrow.isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("pending", "retry", "running", "succeeded")
    job_id = body["job_id"]

    get0 = client.get(
        f"/student/agent/plan-review-jobs/{job_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get0.status_code == 200
    assert get0.json()["status"] in ("pending", "retry", "running", "succeeded")

    PlanReviewJobRunner().run_pending(db_session, limit=10)
    db_session.commit()

    get1 = client.get(
        f"/student/agent/plan-review-jobs/{job_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get1.status_code == 200
    done = get1.json()
    assert done["status"] == "succeeded"
    assert (done.get("created_count") or 0) + (done.get("skipped_count") or 0) >= 0

    job = db_session.get(PlanReviewJob, job_id)
    assert job is not None
    assert job.status == "succeeded"
