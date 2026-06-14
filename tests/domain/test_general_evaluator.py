from src.domain.evaluators.code_review import CodeReviewEvaluator
from src.domain.evaluators.general import GeneralEvaluator
from src.schemas.evaluation import EvaluationSchema


def test_general_evaluator_returns_valid_response():
    evaluator = GeneralEvaluator()
    response = evaluator.evaluate(
        EvaluationSchema(
            id="g1",
            type="general",
            payload={"user_input": "hello world"},
            metadata={},
        )
    )
    assert response.is_valid is True
    assert "hello world" in response.data


def test_code_review_delegates_to_code_evaluator(mock_llm):
    evaluator = CodeReviewEvaluator(client=mock_llm)
    response = evaluator.evaluate(
        EvaluationSchema(
            id="cr1",
            type="code_review",
            payload={
                "code": "def add(a, b):\n    return a + b",
                "expected_output": "语法正确",
            },
            metadata={},
        )
    )
    assert response.is_valid is True
    assert response.metadata["syntax_valid"] is True
    mock_llm.chat.assert_called_once()
