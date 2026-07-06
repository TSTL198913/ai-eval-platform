"""Phase 3: 评估服务重构测试"""
import pytest
from unittest.mock import Mock, patch

from src.services.evaluator_svc import EvaluatorService, EvaluationServiceResponse


class TestEvaluatorServiceRefactored:
    def test_run_evaluation_with_external_clients(self):
        mock_engine = Mock()
        mock_result = Mock()
        mock_result.status.value = "passed"
        mock_result.latency_ms = 1234.5
        mock_result.response = Mock()
        mock_result.response.model_dump.return_value = {"score": 0.95}
        mock_engine.run.return_value = mock_result

        service = EvaluatorService(engine=mock_engine)

        mock_client = Mock()
        mock_inference_client = Mock()

        result = service.run_evaluation(
            {
                "type": "qa",
                "id": "test-001",
                "payload": {"prompt": "test", "actual_output": "output", "expected_output": "expected"},
            },
            client=mock_client,
            inference_client=mock_inference_client,
        )

        assert isinstance(result, EvaluationServiceResponse)
        assert result.api_response["status"] == "success"
        assert result.api_response["record_id"] == "test-001"
        assert result.api_response["evaluation_status"] == "passed"
        assert result.api_response["latency_ms"] == 1234.5
        assert "persist" not in result.api_response
        assert result.domain_result is not None

    def test_run_evaluation_error(self):
        mock_engine = Mock()
        mock_result = Mock()
        mock_result.status.value = "error"
        mock_result.latency_ms = 100.0
        mock_result.error_message = "Evaluation failed"
        mock_result.response = None
        mock_engine.run.return_value = mock_result

        service = EvaluatorService(engine=mock_engine)

        result = service.run_evaluation(
            {
                "type": "qa",
                "id": "test-error",
                "payload": {"prompt": "test"},
            },
            client=Mock(),
        )

        assert isinstance(result, EvaluationServiceResponse)
        assert result.api_response["status"] == "error"
        assert result.api_response["code"] == "EVALUATION_ERROR"
        assert result.api_response["message"] == "Evaluation failed"

    def test_run_evaluation_no_engine_provided(self):
        mock_client = Mock()

        service = EvaluatorService()

        with patch("src.services.evaluator_svc.EvaluationEngine") as MockEngine:
            mock_engine_instance = Mock()
            mock_result = Mock()
            mock_result.status.value = "passed"
            mock_result.latency_ms = 500.0
            mock_result.response = Mock()
            mock_result.response.model_dump.return_value = {"score": 0.8}
            mock_engine_instance.run.return_value = mock_result
            MockEngine.return_value = mock_engine_instance

            result = service.run_evaluation(
                {
                    "type": "qa",
                    "id": "test-no-engine",
                    "payload": {"prompt": "test", "actual_output": "output", "expected_output": "expected"},
                },
                client=mock_client,
            )

            MockEngine.assert_called_once_with(mock_client, inference_client=None)
            assert isinstance(result, EvaluationServiceResponse)
            assert result.api_response["status"] == "success"