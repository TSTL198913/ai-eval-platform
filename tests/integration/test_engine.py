from unittest.mock import MagicMock

import pytest
from src.domain.evaluators.base import EvaluatorFactory
from src.engine import EvaluationEngine
from src.schemas.evaluation import EvaluationSchema, EvaluationStatus


def test_evaluator_factory():
    evaluator = EvaluatorFactory.get("finance", client=MagicMock())
    assert evaluator is not None


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.config = MagicMock()
    client.config.model_name = "test-model"
    client.chat.return_value = "利息为30元"
    return client


def test_engine_happy_path(mock_client):
    engine = EvaluationEngine(mock_client)

    request = EvaluationSchema(
        id="001",
        type="finance",
        payload={
            "case_id": "001",
            "user_input": "请计算1000元贷款利息",
            "expected_output": "30",
            "domain": "finance",
        },
        metadata={},
    )

    result = engine.run(request)
    assert result.status == EvaluationStatus.PASSED
    assert result.adapter_name == "FinanceEvaluator"
    assert result.response.is_valid is True
    mock_client.chat.assert_called_once()
