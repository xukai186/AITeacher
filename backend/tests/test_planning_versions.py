from app.models import MasterPlan, SubjectPlan
from app.services.planning import PlanningService
from tests.test_placement_flow import _seed_student


def test_planning_creates_master_and_subject_plans(db_session):
    student = _seed_student(db_session)
    PlanningService().create_initial_plans(db_session, student_user_id=student.id)
    assert db_session.query(MasterPlan).count() == 1
    assert db_session.query(SubjectPlan).count() == 1

