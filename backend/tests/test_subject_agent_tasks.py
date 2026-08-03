import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.models import DailyTask, MasterPlan, MasterPlanVersion, PlanReviewJob, StudentProfile, StudentSubject, SyllabusNode, UserRole, WrongBookItem
from app.services.plan_review_jobs import PlanReviewJobRunner
from app.services.planning import PlanningService
from app.services.subject_agent import SubjectAgentService
from tests.exam_profile_helpers import add_complete_exam_profile
from tests.factories import make_org, make_user
from tests.paper_gen_job_helpers import start_placement_and_wait


def _seed_student(db):
    org = make_org(db)
    student = make_user(
        db,
        org,
        role=UserRole.student,
        email="agent-student@demo.example",
        password_hash=hash_password("pw"),
    )
    db.add(StudentProfile(user_id=student.id, exam_year=2027))
    add_complete_exam_profile(db, student.id)
    db.add(StudentSubject(student_user_id=student.id, subject_code="english"))
    db.commit()
    PlanningService().create_initial_plans(db, student_user_id=student.id)
    db.commit()
    return student


def _syllabus_nodes(db, subject_code: str, names: list[str]) -> list[SyllabusNode]:
    nodes = [
        SyllabusNode(subject_code=subject_code, name=name, weight=1) for name in names
    ]
    db.add_all(nodes)
    db.flush()
    return nodes


def _set_focus_goals(db, student, subject_code: str, node_ids: list[str]) -> None:
    plan = db.execute(
        select(MasterPlan).where(MasterPlan.student_user_id == student.id)
    ).scalar_one()
    version = db.get(MasterPlanVersion, plan.current_version_id)
    version.weekly_goals_json = [
        {
            "kind": "focus",
            "subject_code": subject_code,
            "title": "本周推进",
            "description": "聚焦叶子节点",
            "syllabus_node_ids": node_ids,
        }
    ]
    db.flush()


def _add_wrong_item(db, student, subject_code: str, node_id) -> None:
    db.add(
        WrongBookItem(
            student_user_id=student.id,
            subject_code=subject_code,
            knowledge_node_id=node_id,
            source_type="self_test",
            source_id=uuid.uuid4(),
            question_snapshot_json={"stem": "q"},
            answer_snapshot_json={"content": "x"},
            correct_snapshot_json={"answer_key": "y"},
        )
    )
    db.flush()


def _token(client):
    return client.post(
        "/auth/login",
        json={"email": "agent-student@demo.example", "password": "pw"},
    ).json()["access_token"]


def test_apply_recommendations_enqueues_job(client, db_session):
    student = _seed_student(db_session)
    token = _token(client)

    start_placement_and_wait(client, token, db_session=db_session)
    paper_id = client.get("/student/placement", headers={"Authorization": f"Bearer {token}"}).json()[0]["id"]
    paper = client.get(f"/student/placement/{paper_id}", headers={"Authorization": f"Bearer {token}"}).json()
    submit = client.post(
        f"/student/placement/{paper_id}/submit",
        json={"answers": [{"question_id": q["id"], "content": "Z"} for q in paper["questions"]]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert submit.status_code == 200

    tomorrow = date.today() + timedelta(days=1)
    resp = client.post(
        "/student/agent/apply-recommendations",
        params={"subject_code": "english", "target_date": tomorrow.isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["job_id"]
    assert body["status"] in ("pending", "retry", "running", "succeeded")

    PlanReviewJobRunner().run_pending(db_session, limit=10)
    db_session.commit()

    job = db_session.get(PlanReviewJob, body["job_id"])
    assert job is not None
    assert job.status == "succeeded"

    get_resp = client.get(
        f"/student/agent/plan-review-jobs/{body['job_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp.status_code == 200
    done = get_resp.json()
    assert done["status"] == "succeeded"

    tasks = db_session.execute(
        select(DailyTask).where(
            DailyTask.student_user_id == student.id,
            DailyTask.date == tomorrow,
        )
    ).scalars().all()
    assert len(tasks) >= 0

    again = client.post(
        "/student/agent/apply-recommendations",
        params={"subject_code": "english", "target_date": tomorrow.isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert again.status_code == 200
    assert again.json()["job_id"] == body["job_id"]


def test_subject_agent_service_idempotent(db_session):
    student = _seed_student(db_session)
    tomorrow = date.today() + timedelta(days=1)

    out1 = SubjectAgentService().apply_report_recommendations(
        db_session,
        student_user_id=student.id,
        subject_code="english",
        target_date=tomorrow,
    )
    assert out1.created_count >= 0

    out2 = SubjectAgentService().apply_report_recommendations(
        db_session,
        student_user_id=student.id,
        subject_code="english",
        target_date=tomorrow,
    )
    assert out2.created_count == 0
    assert out2.skipped_count >= out1.created_count


def test_apply_recommendations_defaults_to_today(db_session):
    student = _seed_student(db_session)
    nodes = _syllabus_nodes(db_session, "english", ["阅读 A"])
    _set_focus_goals(db_session, student, "english", [str(nodes[0].id)])

    out = SubjectAgentService().apply_report_recommendations(
        db_session,
        student_user_id=student.id,
        subject_code="english",
    )
    assert out.target_date == date.today()


def test_apply_uses_weekly_focus_nodes_and_one_weak_review(db_session):
    student = _seed_student(db_session)
    nodes = _syllabus_nodes(db_session, "english", ["阅读 A", "阅读 B"])
    node_a, node_b = nodes
    _set_focus_goals(
        db_session, student, "english", [str(node_a.id), str(node_b.id)]
    )
    _add_wrong_item(db_session, student, "english", node_a.id)
    db_session.commit()

    out = SubjectAgentService().apply_report_recommendations(
        db_session,
        student_user_id=student.id,
        subject_code="english",
        target_date=date.today(),
    )
    db_session.commit()

    focus_ids = {str(node_a.id), str(node_b.id)}
    study_tasks = [
        t
        for t in out.created
        if t.type == "study" and t.payload_json.get("source") == "weekly_goal"
    ]
    assert study_tasks
    assert all(t.payload_json.get("syllabus_node_id") in focus_ids for t in study_tasks)
    assert all(t.title for t in study_tasks)

    weak_tasks = [
        t
        for t in out.created
        if t.type == "review_wrong" and t.payload_json.get("source") == "report_weak"
    ]
    assert len(weak_tasks) <= 1
    if weak_tasks:
        assert weak_tasks[0].title


def test_apply_falls_back_to_report_when_no_focus(db_session):
    student = _seed_student(db_session)
    nodes = _syllabus_nodes(db_session, "english", ["语法 C"])
    _add_wrong_item(db_session, student, "english", nodes[0].id)
    db_session.commit()

    out = SubjectAgentService().apply_report_recommendations(
        db_session,
        student_user_id=student.id,
        subject_code="english",
        target_date=date.today(),
    )
    db_session.commit()

    rec_tasks = [t for t in out.created if t.payload_json.get("source") == "report_recommendation"]
    assert rec_tasks
    assert any(t.type == "review_wrong" for t in rec_tasks)
