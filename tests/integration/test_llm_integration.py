from src.domain.evaluators.base import EvaluatorFactory
from src.schemas.evaluation import DomainResponse, EvaluationSchema


def test_finance_evaluator_via_factory(mock_llm):
    evaluator = EvaluatorFactory.get("finance", client=mock_llm)
    request = EvaluationSchema(
        id="001",
        type="finance",
        payload={
            "user_input": "请计算1000元一年期贷款利息",
            "expected_output": "30",
        },
        metadata={},
    )

    response = evaluator.evaluate(request)

    assert isinstance(response, DomainResponse)
    assert response.is_valid is True
    assert response.text is not None
    mock_llm.chat.assert_called_once()
