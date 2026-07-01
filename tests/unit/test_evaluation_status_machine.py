import pytest
from unittest.mock import patch, MagicMock

from src.schemas.evaluation import (
    DomainResponse,
    EvaluatorStatus,
    ConfidenceLevel,
    EvaluationSchema,
)
from src.domain.evaluators.base import BaseEvaluator


class TestEvaluator(BaseEvaluator):
    """用于测试的评估器子类"""

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        return DomainResponse(score=1.0)


class TestDomainResponseStatusMachine:
    """测试 DomainResponse 状态机逻辑"""

    def test_is_valid_derived_from_status_success(self):
        response = DomainResponse(
            evaluation_status=EvaluatorStatus.SUCCESS,
            confidence=0.9,
        )
        assert response.is_valid is True
        assert response.confidence_level == ConfidenceLevel.HIGH

    def test_is_valid_derived_from_status_partial(self):
        response = DomainResponse(
            evaluation_status=EvaluatorStatus.PARTIAL,
            confidence=0.7,
        )
        assert response.is_valid is True
        assert response.confidence_level == ConfidenceLevel.MEDIUM

    def test_is_valid_derived_from_status_cannot_evaluate(self):
        response = DomainResponse(
            evaluation_status=EvaluatorStatus.CANNOT_EVALUATE,
        )
        assert response.is_valid is False
        assert response.confidence is None

    def test_is_valid_derived_from_status_error(self):
        response = DomainResponse(
            evaluation_status=EvaluatorStatus.ERROR,
            error="test error",
        )
        assert response.is_valid is False

    def test_confidence_level_auto_computed_high(self):
        response = DomainResponse(confidence=0.95)
        assert response.confidence_level == ConfidenceLevel.HIGH

    def test_confidence_level_auto_computed_medium(self):
        response = DomainResponse(confidence=0.75)
        assert response.confidence_level == ConfidenceLevel.MEDIUM

    def test_confidence_level_auto_computed_low(self):
        response = DomainResponse(confidence=0.55)
        assert response.confidence_level == ConfidenceLevel.LOW

    def test_confidence_level_auto_computed_very_low(self):
        response = DomainResponse(confidence=0.3)
        assert response.confidence_level == ConfidenceLevel.VERY_LOW

    def test_confidence_level_not_overwritten_when_provided(self):
        response = DomainResponse(
            confidence=0.95,
            confidence_level=ConfidenceLevel.LOW,
        )
        assert response.confidence_level == ConfidenceLevel.LOW


class TestEvaluatorResponseFactory:
    """测试评估器响应工厂方法"""

    def test_create_success_response_has_correct_status(self):
        evaluator = TestEvaluator()
        response = evaluator.create_success_response(
            text="test",
            score=0.85,
        )
        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.is_valid is True
        assert response.confidence == 0.95

    def test_create_error_response_has_correct_status(self):
        evaluator = TestEvaluator()
        response = evaluator.create_error_response(
            error_message="test error",
            error_code="TEST_ERROR",
        )
        assert response.evaluation_status == EvaluatorStatus.ERROR
        assert response.is_valid is False
        assert response.confidence == 0.0
        assert response.metadata == {"error_code": "TEST_ERROR"}

    def test_create_cannot_evaluate_response_has_correct_status(self):
        evaluator = TestEvaluator()
        response = evaluator.create_cannot_evaluate_response(
            reason="missing input",
        )
        assert response.evaluation_status == EvaluatorStatus.CANNOT_EVALUATE
        assert response.is_valid is False
        assert response.score is None

    def test_create_partial_response_has_correct_status(self):
        evaluator = TestEvaluator()
        response = evaluator.create_partial_response(
            text="partial result",
            score=0.7,
            dimensions_evaluated=["dim1"],
            dimensions_skipped=["dim2"],
        )
        assert response.evaluation_status == EvaluatorStatus.PARTIAL
        assert response.is_valid is True
        assert "dimensions_evaluated" in response.data
        assert "dimensions_skipped" in response.data


class TestEvaluationStatusMapping:
    """测试状态转换规则"""

    def test_status_mapping_success_to_passed(self):
        response = DomainResponse(evaluation_status=EvaluatorStatus.SUCCESS)
        assert response.is_valid is True

    def test_status_mapping_partial_to_passed(self):
        response = DomainResponse(evaluation_status=EvaluatorStatus.PARTIAL)
        assert response.is_valid is True

    def test_status_mapping_cannot_evaluate_to_error(self):
        response = DomainResponse(evaluation_status=EvaluatorStatus.CANNOT_EVALUATE)
        assert response.is_valid is False

    def test_status_mapping_error_to_failed(self):
        response = DomainResponse(evaluation_status=EvaluatorStatus.ERROR)
        assert response.is_valid is False


class TestEvaluationLogging:
    """测试评估日志记录"""

    @patch("src.domain.evaluators.base.logger")
    def test_log_evaluation_result_called(self, mock_logger):
        evaluator = TestEvaluator()
        request = EvaluationSchema(
            id="test-123",
            type="general",
            payload={"user_input": "hello"},
        )
        response = DomainResponse(
            evaluation_status=EvaluatorStatus.SUCCESS,
            score=0.85,
            confidence=0.9,
        )
        evaluator._log_evaluation_result(request, response)
        mock_logger.info.assert_called_once()


class TestConfidenceCalculation:
    """测试置信度计算逻辑"""

    def test_partial_response_confidence_based_on_coverage(self):
        evaluator = TestEvaluator()
        response = evaluator.create_partial_response(
            text="test",
            score=0.7,
            dimensions_evaluated=["dim1", "dim2"],
            dimensions_skipped=["dim3"],
            evaluation_method="llm",
        )
        expected_confidence = 0.7 * (2 / 3) + 0.25
        assert abs(response.confidence - expected_confidence) < 0.01

    def test_partial_response_confidence_embedding_method(self):
        evaluator = TestEvaluator()
        response = evaluator.create_partial_response(
            text="test",
            score=0.7,
            dimensions_evaluated=["dim1"],
            dimensions_skipped=["dim2", "dim3"],
            evaluation_method="embedding",
        )
        expected_confidence = 0.5 * (1 / 3) + 0.3
        assert abs(response.confidence - expected_confidence) < 0.01

    def test_partial_response_confidence_heuristic_method(self):
        evaluator = TestEvaluator()
        response = evaluator.create_partial_response(
            text="test",
            score=0.7,
            dimensions_evaluated=["dim1"],
            dimensions_skipped=[],
            evaluation_method="heuristic",
        )
        expected_confidence = 0.3 * 1.0 + 0.2
        assert abs(response.confidence - expected_confidence) < 0.01