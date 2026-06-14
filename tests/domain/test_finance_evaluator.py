
from src.domain.evaluators.finance import FinanceEvaluator
from src.domain.evaluators.scoring import PASS_THRESHOLD
from src.schemas.evaluation import DomainResponse, EvaluationSchema


def test_finance_evaluator_calls_llm(mock_llm):
    evaluator = FinanceEvaluator(client=mock_llm)
    request = EvaluationSchema(
        id="TEST_LLM",
        type="finance",
        payload={
            "user_input": "请计算1000元贷款利息，年化3%，期限1年",
            "expected_output": "利息为30元",
        },
        metadata={"rate": 0.03},
    )

    response = evaluator.evaluate(request)

    assert isinstance(response, DomainResponse)
    mock_llm.chat.assert_called_once()
    assert response.is_valid is True
    assert response.score >= PASS_THRESHOLD
    assert "30" in response.text


def test_finance_evaluator_fails_when_score_low(mock_llm):
    mock_llm.chat.return_value = "无法计算"
    evaluator = FinanceEvaluator(client=mock_llm)

    request = EvaluationSchema(
        id="TEST_FAIL",
        type="finance",
        payload={
            "user_input": "计算利息",
            "expected_output": "利息为30元",
        },
        metadata={},
    )

    response = evaluator.evaluate(request)
    assert response.is_valid is False
    assert response.score < PASS_THRESHOLD


def test_finance_evaluator_requires_client():
    evaluator = FinanceEvaluator(client=None)
    request = EvaluationSchema(
        id="TEST_NO_CLIENT",
        type="finance",
        payload={"user_input": "测试"},
        metadata={},
    )

    response = evaluator.evaluate(request)
    assert response.is_valid is False
    assert "LLM client" in response.error


def test_finance_evaluator_empty_input(mock_llm):
    evaluator = FinanceEvaluator(client=mock_llm)
    response = evaluator.evaluate(
        EvaluationSchema(
            id="empty",
            type="finance",
            payload={"user_input": ""},
            metadata={},
        )
    )
    assert response.is_valid is False
    assert "不能为空" in response.error
    mock_llm.chat.assert_not_called()
