from app.models import RoadmapGenerationJob
from app.services.roadmap_activation import RoadmapActivationService
from app.services.roadmap_draft import RoadmapDraftService
from app.services.roadmap_generation_jobs import RoadmapGenerationJobRunner, RoadmapGenerationJobService
from tests.factories import make_user
from tests.test_placement_flow import _seed_student, start_placement_and_wait


def test_roadmap_draft_rule_has_months(db_session):
    student = _seed_student(db_session)
    draft = RoadmapDraftService().draft(db_session, student_user_id=student.id)
    months = draft.months_json.get("months") or []
    assert months
    assert months[0]["subjects"]


def test_placement_submit_enqueues_roadmap_when_all_subjects_done(client, db_session):
    student = _seed_student(db_session)
    token = client.post(
        "/auth/login",
        json={"email": student.email, "password": "pw"},
    ).json()["access_token"]
    start_placement_and_wait(client, token, db_session=db_session)
    paper_id = client.get("/student/placement", headers={"Authorization": f"Bearer {token}"}).json()[0]["id"]
    detail = client.get(
        f"/student/placement/{paper_id}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    answers = [
        {"question_id": q["id"], "content": q["choices"][0]["key"] if q.get("choices") else "A"}
        for q in detail["questions"]
    ]
    out = client.post(
        f"/student/placement/{paper_id}/submit",
        headers={"Authorization": f"Bearer {token}"},
        json={"answers": answers},
    ).json()
    assert out["all_placement_complete"] is True
    assert out["roadmap_job_id"] is not None
    state = RoadmapActivationService().get_state(db_session, student_user_id=student.id)
    assert state["pending_version"] is not None


def test_roadmap_confirm_creates_master_plan(client, db_session):
    student = _seed_student(db_session)
    job = RoadmapGenerationJobService().enqueue(db_session, student_user_id=student.id)
    RoadmapGenerationJobService().run_job(db_session, job.job_id)
    token = client.post(
        "/auth/login",
        json={"email": student.email, "password": "pw"},
    ).json()["access_token"]
    confirm = client.post(
        "/student/roadmap/confirm",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert confirm.status_code == 200
    master = client.get("/student/master-plan", headers={"Authorization": f"Bearer {token}"})
    assert master.status_code == 200
    assert master.json()["active_version"] is not None


def test_roadmap_runner_processes_pending(db_session):
    student = _seed_student(db_session)
    job = RoadmapGenerationJobService().enqueue(db_session, student_user_id=student.id)
    from app.services.roadmap_generation_jobs import RoadmapGenerationJobRunner

    ran = RoadmapGenerationJobRunner().run_pending(db_session, limit=10)
    assert ran == 1
    state = RoadmapActivationService().get_state(db_session, student_user_id=student.id)
    assert state["pending_version"] is not None
    assert db_session.get(RoadmapGenerationJob, job.job_id).status == "succeeded"


def test_org_regenerate_roadmap(client, db_session):
    from app.auth.security import hash_password
    from app.models import Organization, StaffStudent, User, UserRole

    student = _seed_student(db_session)
    student_user = db_session.get(User, student.id)
    org = db_session.get(Organization, student_user.org_id)
    staff = make_user(
        db_session,
        org,
        role=UserRole.org_staff,
        email="staff-road@demo.example",
        password_hash=hash_password("pw"),
    )
    db_session.add(StaffStudent(staff_user_id=staff.id, student_user_id=student.id))
    db_session.commit()
    token = client.post(
        "/auth/login",
        json={"email": staff.email, "password": "pw"},
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    regen = client.post(f"/org/students/{student.id}/roadmap/regenerate", headers=headers)
    assert regen.status_code == 200
    assert regen.json()["created"] is True

    view = client.get(f"/org/students/{student.id}/roadmap", headers=headers)
    assert view.status_code == 200
    assert view.json()["pending_version"] is not None
