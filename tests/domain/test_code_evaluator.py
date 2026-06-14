from src.domain.evaluators.code import CodeEvaluator
from src.domain.evaluators.scoring import PASS_THRESHOLD
from src.schemas.evaluation import DomainResponse, EvaluationSchema


def test_code_evaluator_syntax_and_review_pass(mock_llm):
    mock_llm.chat.return_value = "语法正确，函数实现简洁，无明显问题。"
    evaluator = CodeEvaluator(client=mock_llm)
    request = EvaluationSchema(
        id="code_001",
        type="code",
        payload={
            "code": "def add(a, b):\n    return a + b",
            "expected_output": "语法正确",
        },
        metadata={"language": "python"},
    )

    response = evaluator.evaluate(request)

    assert isinstance(response, DomainResponse)
    assert response.is_valid is True
    assert response.score >= PASS_THRESHOLD
    assert response.metadata["syntax_valid"] is True
    mock_llm.chat.assert_called_once()


def test_code_evaluator_syntax_error(mock_llm):
    evaluator = CodeEvaluator(client=mock_llm)
    request = EvaluationSchema(
        id="code_002",
        type="code",
        payload={"code": "def broken(:\n    pass"},
        metadata={},
    )

    response = evaluator.evaluate(request)
    assert response.is_valid is False
    assert "语法错误" in response.error
    mock_llm.chat.assert_not_called()


def test_code_evaluator_requires_client():
    evaluator = CodeEvaluator(client=None)
    response = evaluator.evaluate(
        EvaluationSchema(
            id="code_003",
            type="code",
            payload={"code": "def ok(): pass"},
            metadata={},
        )
    )
    assert response.is_valid is False
    assert "LLM client" in response.error
