from app.models import WrongBookItem
from app.models.self_test import SelfTestAnswer, SelfTestGrade, SelfTestPaper, SelfTestQuestion, SelfTestSubmission


def test_imports_exist():
    assert SelfTestPaper
    assert SelfTestQuestion
    assert SelfTestSubmission
    assert SelfTestAnswer
    assert SelfTestGrade
    assert WrongBookItem

