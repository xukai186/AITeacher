from app.services.placement_grading import (
    PlacementGradeableQuestion,
    grade_placement_answer,
    normalize_answer_key,
    normalize_student_answer,
)


def test_normalize_multi_choice_answer():
    assert normalize_student_answer("B,A", "multi_choice") == "AB"
    assert normalize_answer_key("BA", "multi_choice") == "AB"


def test_grade_fill_blank_case_insensitive(db_session):
    from tests.factories import make_org

    org = make_org(db_session)
    q = PlacementGradeableQuestion(
        q_type="fill_blank",
        stem="填空",
        answer_key=" 2 ",
        points=4,
    )
    score, ok, _ = grade_placement_answer(db_session, org_id=org.id, question=q, content="2")
    assert ok is True
    assert score == 4


def test_grade_short_answer_uses_mock_grader(db_session):
    from tests.factories import make_org

    org = make_org(db_session)
    q = PlacementGradeableQuestion(
        q_type="short_answer",
        stem="证明题",
        answer_key="",
        points=10,
        rubric_json={"keywords": ["极限", "连续"]},
    )
    score, ok, detail = grade_placement_answer(
        db_session, org_id=org.id, question=q, content="包含极限与连续相关论述"
    )
    assert score >= 0
    assert detail is not None
