from app.models import QuestionBankItem, MediaAsset, SelfTestQuestion


def test_question_bank_models_importable():
    assert QuestionBankItem.__tablename__ == "question_bank_items"
    assert MediaAsset.__tablename__ == "media_assets"
    assert hasattr(SelfTestQuestion, "bank_item_id")
    assert hasattr(SelfTestQuestion, "selection_source")
