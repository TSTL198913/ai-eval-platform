from unittest.mock import MagicMock

import pytest

from src.domain.evaluators.base import EvaluatorFactory
from src.engine import EvaluationEngine
from src.schemas.evaluation import DomainResponse, EvaluationSchema, EvaluationStatus


def test_engine_returns_failed_when_score_low(mock_llm):
    mock_llm.chat.return_value = "完全无关的回答"
    engine = EvaluationEngine(mock_llm)

    result = engine.run(
        EvaluationSchema(
            id="fail_001",
            type="finance",
            payload={
                "user_input": "计算利息",
                "expected_output": "30",
            },
            metadata={},
        )
    )

    assert result.status == EvaluationStatus.FAILED
    assert result.response.is_valid is False
    assert result.adapter_name == "FinanceEvaluator"


def test_engine_returns_error_on_unknown_evaluator_type(mock_llm):
    engine = EvaluationEngine(mock_llm)

    result = engine.run(
        EvaluationSchema(
            id="err_001",
            type="not_registered",
            payload={"user_input": "x"},
            metadata={},
        )
    )

    assert result.status == EvaluationStatus.ERROR
    assert result.adapter_name == "error_handler"
    assert "未找到" in result.response.error


def test_evaluator_factory_raises_for_unknown_type():
    with pytest.raises(ValueError, match="未找到"):
        EvaluatorFactory.get("invalid_type", client=MagicMock())


def test_safe_evaluate_wraps_exception():
    from src.domain.evaluators.general import GeneralEvaluator

    class BrokenEvaluator(GeneralEvaluator):
        def evaluate(self, request):
            raise RuntimeError("boom")

    evaluator = BrokenEvaluator()
    response = evaluator.safe_evaluate(
        EvaluationSchema(
            id="1",
            type="general",
            payload={"user_input": "x"},
            metadata={},
        )
    )
    assert isinstance(response, DomainResponse)
    assert response.is_valid is False
    assert "boom" in response.error


def test_get_input_text_prefers_user_input():
    from src.domain.evaluators.general import GeneralEvaluator

    evaluator = GeneralEvaluator()
    request = EvaluationSchema(
        id="1",
        type="general",
        payload={"user_input": "from_user", "text": "from_text"},
        metadata={},
    )
    assert evaluator.get_input_text(request) == "from_user"


def test_get_input_text_falls_back_to_text():
    from src.domain.evaluators.general import GeneralEvaluator

    evaluator = GeneralEvaluator()
    request = EvaluationSchema(
        id="1",
        type="general",
        payload={"text": "from_text"},
        metadata={},
    )
    assert evaluator.get_input_text(request) == "from_text"
