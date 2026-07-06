"""Phase 3: v2 API 路由测试"""
import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from src.api.server import app


class TestV2ApiRoutes:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_inference_endpoint_exists(self, client):
        response = client.post("/api/v2/inference", json={"prompt": "test"})
        assert response.status_code in [200, 422, 500]

    def test_evaluate_endpoint_exists(self, client):
        response = client.post(
            "/api/v2/evaluate",
            json={
                "type": "qa",
                "payload": {"prompt": "test", "actual_output": "output", "expected_output": "expected"},
            },
        )
        assert response.status_code in [200, 422, 500]

    def test_inference_endpoint_with_model_config(self, client):
        with patch("src.api.routes.v2.evaluate.ClientFactoryService.create_eval_client") as mock_create:
            mock_client = Mock()
            mock_client.config.provider = "deepseek"
            mock_client.config.model_name = "deepseek-chat"
            mock_create.return_value = (mock_client, None)

            with patch("src.api.routes.v2.evaluate.InferenceService") as MockService:
                mock_service = Mock()
                mock_service.generate.return_value = "generated output"
                MockService.return_value = mock_service

                response = client.post(
                    "/api/v2/inference",
                    json={"prompt": "test prompt", "model_provider": "deepseek", "model_name": "deepseek-chat"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["code"] == 0
                assert data["data"]["output"] == "generated output"
                assert data["data"]["model_provider"] == "deepseek"
                assert data["data"]["model_name"] == "deepseek-chat"

    def test_evaluate_endpoint_offline_mode(self, client):
        with patch("src.api.routes.v2.evaluate.ClientFactoryService.create_clients") as mock_create:
            mock_eval_client = Mock()
            mock_create.return_value = (mock_eval_client, None, None)

            with patch("src.api.routes.v2.evaluate.EvaluatorService") as MockService:
                mock_service = Mock()
                mock_response = Mock()
                mock_response.api_response = {
                    "status": "success",
                    "record_id": "test-001",
                    "evaluation_status": "passed",
                    "latency_ms": 1234.5,
                    "data": {"score": 0.95},
                }
                mock_response.domain_result = Mock()
                mock_service.run_evaluation.return_value = mock_response
                MockService.return_value = mock_service

                response = client.post(
                    "/api/v2/evaluate",
                    json={
                        "type": "qa",
                        "payload": {
                            "prompt": "test",
                            "actual_output": "the answer",
                            "expected_output": "expected answer",
                        },
                        "evaluate_mode": "offline",
                    },
                )

                assert response.status_code == 200
                data = response.json()
                assert data["code"] == 0
                assert data["data"]["evaluation_status"] == "passed"

    def test_evaluate_endpoint_with_separate_models(self, client):
        with patch("src.api.routes.v2.evaluate.ClientFactoryService.create_clients") as mock_create:
            mock_eval_client = Mock()
            mock_inference_client = Mock()
            mock_create.return_value = (mock_eval_client, mock_inference_client, None)

            with patch("src.api.routes.v2.evaluate.EvaluatorService") as MockService:
                mock_service = Mock()
                mock_response = Mock()
                mock_response.api_response = {
                    "status": "success",
                    "record_id": "test-separate-models",
                    "evaluation_status": "passed",
                    "latency_ms": 2000.0,
                    "data": {"score": 0.9},
                }
                mock_response.domain_result = Mock()
                mock_service.run_evaluation.return_value = mock_response
                MockService.return_value = mock_service

                response = client.post(
                    "/api/v2/evaluate",
                    json={
                        "type": "qa",
                        "payload": {"prompt": "test", "actual_output": "output", "expected_output": "expected"},
                        "model_provider": "deepseek",
                        "model_name": "deepseek-chat",
                        "inference_model_provider": "openai",
                        "inference_model_name": "gpt-4",
                    },
                )

                assert response.status_code == 200
                mock_create.assert_called_once()

    def test_evaluate_endpoint_idempotency(self, client):
        with patch("src.api.routes.v2.evaluate._get_idempotency_checker") as mock_get_checker:
            mock_checker = Mock()
            mock_checker.get_cached_result.return_value = None
            mock_checker.mark_processing.return_value = True
            mock_get_checker.return_value = mock_checker

            with patch("src.api.routes.v2.evaluate.ClientFactoryService.create_clients") as mock_create:
                mock_eval_client = Mock()
                mock_create.return_value = (mock_eval_client, None, None)

                with patch("src.api.routes.v2.evaluate.EvaluatorService") as MockService:
                    mock_service = Mock()
                    mock_response = Mock()
                    mock_response.api_response = {
                        "status": "success",
                        "record_id": "test-idempotency",
                        "evaluation_status": "passed",
                        "latency_ms": 500.0,
                        "data": {"score": 0.85},
                    }
                    mock_response.domain_result = Mock()
                    mock_service.run_evaluation.return_value = mock_response
                    MockService.return_value = mock_service

                    response = client.post(
                        "/api/v2/evaluate",
                        json={
                            "id": "test-request-001",
                            "type": "qa",
                            "payload": {"prompt": "test", "actual_output": "output", "expected_output": "expected"},
                        },
                    )

                    assert response.status_code == 200
                    mock_checker.mark_processing.assert_called_once_with("test-request-001")
                    mock_checker.mark_processed.assert_called_once()