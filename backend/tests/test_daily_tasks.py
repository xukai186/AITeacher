from datetime import date

from app.auth.security import hash_password
from app.models import DailyTask, StudentProfile, StudentSubject, UserRole
from app.services.tasks import TaskGenerator
from tests.factories import make_org, make_user


def test_generate_7_days_tasks(db_session):
    org = make_org(db_session)
    student = make_user(
        db_session,
        org,
        role=UserRole.student,
        email="s@demo.example",
        password_hash=hash_password("pw"),
    )
    db_session.add(StudentProfile(user_id=student.id, exam_year=2027))
    db_session.add(StudentSubject(student_user_id=student.id, subject_code="english"))
    db_session.commit()

    gen = TaskGenerator()
    gen.generate_next_7_days(db_session, student_user_id=student.id, today=date.today())
    assert db_session.query(DailyTask).count() == 7

    gen.generate_next_7_days(db_session, student_user_id=student.id, today=date.today())
    assert db_session.query(DailyTask).count() == 7


def test_generate_7_days_tasks_all_subjects(db_session):
    org = make_org(db_session)
    student = make_user(
        db_session,
        org,
        role=UserRole.student,
        email="s2@demo.example",
        password_hash=hash_password("pw"),
    )
    db_session.add(StudentProfile(user_id=student.id, exam_year=2027))
    for code in ("english", "math", "politics"):
        db_session.add(StudentSubject(student_user_id=student.id, subject_code=code))
    db_session.commit()

    TaskGenerator().generate_next_7_days(db_session, student_user_id=student.id, today=date.today())
    assert db_session.query(DailyTask).count() == 21

