from sqlalchemy import select

from app.auth.security import hash_password
from app.models import ModelPolicy, StudentProfile, StudentSubject, UserRole
from app.services.chat_tool_executor import ChatToolExecutor
from app.services.paper_gen_jobs import PaperGenJobRunner
from app.services.placement import PlacementService
from app.services.self_test import SelfTestService
from app.services.planning import PlanningService
from tests.exam_profile_helpers import add_complete_exam_profile
from tests.factories import make_org, make_user


def _seed_student(db):
    org = make_org(db)
    student = make_user(
        db,
        org,
        role=UserRole.student,
        email="chat-papers@demo.example",
        password_hash=hash_password("pw"),
    )
    db.add(StudentProfile(user_id=student.id, exam_year=2027))
    add_complete_exam_profile(db, student.id)
    db.add(StudentSubject(student_user_id=student.id, subject_code="english", enabled=True))
    db.add(ModelPolicy(org_id=org.id, scene="chat", provider="mock", model="mock-v1", params={}))
    db.add(ModelPolicy(org_id=org.id, scene="paper_gen", provider="mock", model="mock-v1", params={}))
    db.commit()
    PlanningService().create_initial_plans(db, student_user_id=student.id)
    db.commit()
    return student


def test_chat_tools_list_and_get_paper(db_session):
    student = _seed_student(db_session)

    # Create one placement paper and one self-test paper.
    out = PlacementService.start(db_session, student.id, subject_code="english")
    if out.gen_job_id is not None:
        PaperGenJobRunner().run_pending(db_session, limit=1, job_id=out.gen_job_id)
        db_session.commit()

    self_paper, gen_job_id = SelfTestService.generate(db_session, student.id, "english", skip_eligibility=True)
    if gen_job_id is not None:
        PaperGenJobRunner().run_pending(db_session, limit=1, job_id=gen_job_id)
        db_session.commit()

    executor = ChatToolExecutor()

    listed = executor.execute(
        db_session,
        tool_name="list_papers",
        arguments={"limit": 5},
        student_user_id=student.id,
        default_subject_code="english",
        agent_type="subject",
    )
    assert listed["subject_code"] == "english"
    assert listed["placement_papers"]
    assert listed["self_test_papers"]

    placement_id = listed["placement_papers"][0]["paper_id"]
    placement = executor.execute(
        db_session,
        tool_name="get_paper",
        arguments={"paper_type": "placement", "paper_id": placement_id},
        student_user_id=student.id,
        default_subject_code="english",
        agent_type="subject",
    )
    assert placement["paper_type"] == "placement"
    assert placement["paper_id"] == placement_id
    assert len(placement["questions"]) > 0

    self_test = executor.execute(
        db_session,
        tool_name="get_paper",
        arguments={"paper_type": "self_test", "paper_id": str(self_paper.id)},
        student_user_id=student.id,
        default_subject_code="english",
        agent_type="subject",
    )
    assert self_test["paper_type"] == "self_test"
    assert self_test["paper_id"] == str(self_paper.id)
    assert len(self_test["questions"]) > 0

