from unittest.mock import MagicMock, patch

from src.exceptions import BasePlatformError
from src.services.evaluator_svc import (
    _normalize_raw_data,
    run_evaluation_service,
    service_exception_handler,
)


class TestServiceExceptionHandler:
    def test_handles_base_platform_error(self):
        @service_exception_handler
        def failing_func():
            raise BasePlatformError(code="TEST_ERROR", message="test error")

        result = failing_func()
        assert result["status"] == "error"
        assert result["code"] == "TEST_ERROR"
        assert result["message"] == "test error"

    def test_handles_validation_error(self):
        @service_exception_handler
        def failing_func():
            class ValidationError(Exception):
                pass

            raise ValidationError("validation failed")

        result = failing_func()
        assert result["status"] == "error"
        assert result["code"] == "CONTRACT_ERROR"

    def test_handles_generic_exception(self):
        @service_exception_handler
        def failing_func():
            raise ValueError("unknown error")

        result = failing_func()
        assert result["status"] == "error"
        assert result["code"] == "INTERNAL_ERROR"

    def test_passes_through_success(self):
        @service_exception_handler
        def success_func():
            return {"status": "success"}

        result = success_func()
        assert result == {"status": "success"}


class TestNormalizeRawData:
    def test_normalizes_without_payload(self):
        raw_data = {
            "id": "test123",
            "type": "qa",
            "input": "hello",
            "output": "world",
            "model_provider": "openai",
        }
        normalized = _normalize_raw_data(raw_data)
        assert normalized["id"] == "test123"
        assert normalized["type"] == "qa"
        assert normalized["payload"] == {"input": "hello", "output": "world"}
        assert normalized["model_provider"] == "openai"

    def test_passes_through_with_payload(self):
        raw_data = {
            "id": "test123",
            "type": "qa",
            "payload": {"input": "hello"},
            "metadata": {"tag": "test"},
        }
        normalized = _normalize_raw_data(raw_data)
        assert normalized == raw_data

    def test_handles_empty_input(self):
        raw_data = {}
        normalized = _normalize_raw_data(raw_data)
        assert normalized["id"] == "unknown"
        assert normalized["payload"] == {}

    def test_strips_id_and_type_from_payload(self):
        raw_data = {
            "id": "test123",
            "type": "qa",
            "input": "hello",
            "id_in_payload": "should_be_included",
        }
        normalized = _normalize_raw_data(raw_data)
        assert "id" not in normalized["payload"]
        assert "type" not in normalized["payload"]
        assert "id_in_payload" in normalized["payload"]


class TestRunEvaluationService:
    @patch("src.services.evaluator_svc.EvaluationSchema")
    @patch("src.services.evaluator_svc._get_evaluator_registry")
    @patch("src.services.evaluator_svc.EvaluationEngine")
    @patch("src.services.evaluator_svc._repository")
    def test_run_evaluation_success(self, mock_repo, mock_engine, mock_registry, mock_schema):
        mock_registry.return_value = {"qa": MagicMock()}
        mock_schema.return_value = MagicMock(
            id="test123", type="qa", payload={}, model_provider="openai", model_name="gpt-4"
        )
        mock_result = MagicMock()
        mock_result.status.value = "success"
        mock_result.error_message = None
        mock_result.response.model_dump.return_value = {"score": 0.8}
        mock_result.latency_ms = 100
        mock_result.case_id = "test123"
        mock_engine.return_value.run.return_value = mock_result
        mock_repo.save.return_value = 1

        result = run_evaluation_service({"type": "qa", "input": "test"})

        assert result["status"] == "success"
        assert result["evaluation_status"] == "success"
        assert result["data"] == {"score": 0.8}
        assert result["persist"] is True

    @patch("src.services.evaluator_svc.EvaluationSchema")
    @patch("src.services.evaluator_svc._get_evaluator_registry")
    def test_run_evaluation_unknown_type(self, mock_registry, mock_schema):
        mock_registry.return_value = {"qa": MagicMock()}
        mock_schema.return_value = MagicMock(id="test123", type="unknown_type")

        result = run_evaluation_service({"type": "unknown_type"})

        assert result["status"] == "error"
        assert result["code"] == "DOMAIN_ERROR"

    @patch("src.services.evaluator_svc.EvaluationSchema")
    @patch("src.services.evaluator_svc._get_evaluator_registry")
    @patch("src.services.evaluator_svc.EvaluationEngine")
    def test_run_evaluation_with_client(self, mock_engine, mock_registry, mock_schema):
        mock_registry.return_value = {"qa": MagicMock()}
        mock_schema.return_value = MagicMock(
            id="test123", type="qa", payload={}, model_provider=None, model_name=None
        )
        mock_result = MagicMock()
        mock_result.status.value = "success"
        mock_result.error_message = None
        mock_result.response.model_dump.return_value = {}
        mock_result.latency_ms = 50
        mock_result.case_id = "test123"
        mock_engine.return_value.run.return_value = mock_result

        mock_client = MagicMock()
        result = run_evaluation_service({"type": "qa"}, client=mock_client)

        assert result["status"] == "success"
        mock_engine.assert_called_with(mock_client)

    @patch("src.services.evaluator_svc.EvaluationSchema")
    @patch("src.services.evaluator_svc._get_evaluator_registry")
    @patch("src.services.evaluator_svc.EvaluationEngine")
    @patch("src.services.evaluator_svc._repository")
    def test_run_evaluation_persist_failure(
        self, mock_repo, mock_engine, mock_registry, mock_schema
    ):
        mock_registry.return_value = {"qa": MagicMock()}
        mock_schema.return_value = MagicMock(
            id="test123", type="qa", payload={}, model_provider="openai", model_name="gpt-4"
        )
        mock_result = MagicMock()
        mock_result.status.value = "success"
        mock_result.error_message = None
        mock_result.response.model_dump.return_value = {}
        mock_result.latency_ms = 50
        mock_result.case_id = "test123"
        mock_engine.return_value.run.return_value = mock_result
        mock_repo.save.side_effect = Exception("DB error")

        result = run_evaluation_service({"type": "qa"})

        assert result["persist"] is False
        assert "DB error" in result["persist_error"]
