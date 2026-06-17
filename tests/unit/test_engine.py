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


def test_engine_handles_contract_validation_error(mock_llm):
    from unittest.mock import patch
    from src.exceptions import ContractValidationError

    with patch("src.domain.evaluators.evaluator_factory.EvaluatorFactory.get") as mock_get:
        mock_get.side_effect = ContractValidationError("invalid input")
        engine = EvaluationEngine(mock_llm)

        result = engine.run(
            EvaluationSchema(
                id="contract_err",
                type="finance",
                payload={"user_input": "test"},
                metadata={},
            )
        )

        assert result.status == EvaluationStatus.ERROR
        assert result.adapter_name == "contract_validator"
        assert "契约验证错误" in result.response.error


def test_engine_handles_domain_logic_error(mock_llm):
    from unittest.mock import patch
    from src.exceptions import DomainLogicError

    with patch("src.domain.evaluators.evaluator_factory.EvaluatorFactory.get") as mock_get:
        mock_get.side_effect = DomainLogicError("domain error")
        engine = EvaluationEngine(mock_llm)

        result = engine.run(
            EvaluationSchema(
                id="domain_err",
                type="finance",
                payload={"user_input": "test"},
                metadata={},
            )
        )

        assert result.status == EvaluationStatus.ERROR
        assert result.adapter_name == "domain_handler"
        assert "领域错误" in result.response.error


def test_engine_handles_infrastructure_error(mock_llm):
    from unittest.mock import patch
    from src.exceptions import InfrastructureError

    with patch("src.domain.evaluators.evaluator_factory.EvaluatorFactory.get") as mock_get:
        mock_get.side_effect = InfrastructureError("db connection failed")
        engine = EvaluationEngine(mock_llm)

        result = engine.run(
            EvaluationSchema(
                id="infra_err",
                type="finance",
                payload={"user_input": "test"},
                metadata={},
            )
        )

        assert result.status == EvaluationStatus.ERROR
        assert result.adapter_name == "infra_handler"
        assert "基础设施错误" in result.response.error


def test_engine_handles_generic_exception(mock_llm):
    from unittest.mock import patch

    with patch("src.domain.evaluators.evaluator_factory.EvaluatorFactory.get") as mock_get:
        mock_get.side_effect = RuntimeError("unexpected error")
        engine = EvaluationEngine(mock_llm)

        result = engine.run(
            EvaluationSchema(
                id="generic_err",
                type="finance",
                payload={"user_input": "test"},
                metadata={},
            )
        )

        assert result.status == EvaluationStatus.ERROR
        assert result.adapter_name == "error_handler"


def test_engine_returns_passed_when_valid(mock_llm):
    mock_llm.chat.return_value = "正确的回答"
    engine = EvaluationEngine(mock_llm)

    result = engine.run(
        EvaluationSchema(
            id="pass_001",
            type="general",
            payload={"user_input": "hello"},
            metadata={},
        )
    )

    assert result.status == EvaluationStatus.PASSED
    assert result.response.is_valid is True
