from src.domain.evaluators.scoring import PASS_THRESHOLD
from src.domain.evaluators.text import TextMatchEvaluator
from src.schemas.evaluation import DomainResponse, EvaluationSchema


def test_text_evaluator_similarity_pass(mock_llm):
    mock_llm.chat.return_value = "机器学习是人工智能的重要分支，用于从数据中学习规律。"
    evaluator = TextMatchEvaluator(client=mock_llm)
    request = EvaluationSchema(
        id="text_001",
        type="text",
        payload={
            "user_input": "什么是机器学习",
            "expected_output": "机器学习是人工智能的重要分支",
        },
        metadata={},
    )

    response = evaluator.evaluate(request)

    assert isinstance(response, DomainResponse)
    assert response.is_valid is True
    assert response.score >= PASS_THRESHOLD
    mock_llm.chat.assert_called_once()


def test_text_evaluator_low_similarity_fail(mock_llm):
    mock_llm.chat.return_value = "今天天气不错。"
    evaluator = TextMatchEvaluator(client=mock_llm)

    request = EvaluationSchema(
        id="text_002",
        type="text",
        payload={
            "text": "解释量子力学",
            "expected_output": "量子力学",
        },
        metadata={},
    )

    response = evaluator.evaluate(request)
    assert response.is_valid is False
    assert response.score < PASS_THRESHOLD


def test_text_evaluator_requires_client():
    evaluator = TextMatchEvaluator(client=None)
    response = evaluator.evaluate(
        EvaluationSchema(
            id="text_003",
            type="text",
            payload={"user_input": "test"},
            metadata={},
        )
    )
    assert response.is_valid is False
    assert "LLM client" in response.error
