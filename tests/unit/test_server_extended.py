import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from src.api.server import app


class TestHealthEndpoint:
    def test_health_check(self):
        client = TestClient(app)
        response = client.get('/health')
        assert response.status_code == 200
        assert response.json()['status'] == 'healthy'

    def test_health_check_service_name(self):
        client = TestClient(app)
        response = client.get('/health')
        assert response.json()['service'] == 'ai-eval-platform'


class TestMetricsEndpoint:
    def test_metrics_endpoint(self):
        client = TestClient(app)
        response = client.get('/metrics')
        assert response.status_code == 200


class TestEchoEndpoint:
    def test_echo_endpoint(self):
        client = TestClient(app)
        response = client.get('/api/v1/test/echo')
        assert response.status_code == 200
        assert response.json()['status'] == 'ok'


class TestEvaluateEndpoint:
    def test_evaluate_valid_request(self):
        client = TestClient(app)
        response = client.post(
            '/api/v1/evaluate',
            json={'id': 'test1', 'type': 'general', 'payload': {'user_input': 'test'}}
        )
        assert response.status_code in [200, 422]

    def test_evaluate_missing_id(self):
        client = TestClient(app)
        response = client.post(
            '/api/v1/evaluate',
            json={'type': 'general', 'payload': {'user_input': 'test'}}
        )
        assert response.status_code in [400, 422]

    def test_evaluate_missing_type(self):
        client = TestClient(app)
        response = client.post(
            '/api/v1/evaluate',
            json={'id': 'test1', 'payload': {'user_input': 'test'}}
        )
        assert response.status_code in [400, 422]

    def test_evaluate_empty_payload(self):
        client = TestClient(app)
        response = client.post(
            '/api/v1/evaluate',
            json={'id': 'test1', 'type': 'general', 'payload': {}}
        )
        assert response.status_code in [200, 422]


class TestAsyncEvaluateEndpoint:
    def test_async_evaluate_valid_request(self):
        client = TestClient(app)
        response = client.post(
            '/api/v1/evaluate/async',
            json={'id': 'test1', 'type': 'general', 'payload': {'user_input': 'test'}}
        )
        assert response.status_code in [200, 400]

    def test_async_evaluate_missing_id(self):
        client = TestClient(app)
        response = client.post(
            '/api/v1/evaluate/async',
            json={'type': 'general', 'payload': {'user_input': 'test'}}
        )
        assert response.status_code == 400


class TestTaskStatusEndpoint:
    @patch('src.api.server._get_celery_app')
    def test_task_status_endpoint(self, mock_get_celery):
        mock_celery = MagicMock()
        mock_result = MagicMock()
        mock_result.state = 'PENDING'
        mock_result.ready.return_value = False
        mock_celery.AsyncResult.return_value = mock_result
        mock_get_celery.return_value = mock_celery
        
        client = TestClient(app)
        response = client.get('/api/v1/tasks/test_task_id')
        assert response.status_code == 200
        assert 'task_id' in response.json()
        assert 'state' in response.json()


class TestDatabaseEndpoint:
    def test_database_endpoint(self):
        client = TestClient(app)
        response = client.get('/api/v1/test/db')
        assert response.status_code == 200
        assert 'status' in response.json()


class TestRecordsEndpoint:
    def test_records_endpoint_default_limit(self):
        client = TestClient(app)
        response = client.get('/api/v1/records')
        assert response.status_code == 200

    def test_records_endpoint_custom_limit(self):
        client = TestClient(app)
        response = client.get('/api/v1/records?limit=5')
        assert response.status_code == 200
