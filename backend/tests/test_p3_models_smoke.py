from app.models import (
    DailyTask,
    MasterPlan,
    MasterPlanVersion,
    MasterySnapshot,
    PlacementPaper,
    SyllabusNode,
    SubjectPlan,
    SubjectPlanVersion,
)


def test_imports_exist():
    assert SyllabusNode
    assert PlacementPaper
    assert MasterySnapshot
    assert MasterPlan
    assert MasterPlanVersion
    assert SubjectPlan
    assert SubjectPlanVersion
    assert DailyTask

