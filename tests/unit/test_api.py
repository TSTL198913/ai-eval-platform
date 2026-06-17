import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from src.api.server import app
from src.domain.models.llm_factory import create_llm_client
from src.domain.models.stub import StubLLMClient
from src.services.evaluator_svc import _normalize_raw_data, run_evaluation_service


@pytest.fixture
def api_client():
    return TestClient(app)


def test_sync_evaluate_success(api_client, mock_llm):
    with patch("src.services.evaluator_svc.create_llm_client", return_value=mock_llm):
        response = api_client.post(
            "/api/v1/evaluate",
            json={
                "id": "api_001",
                "type": "finance",
                "payload": {
                    "user_input": "1000元贷款3%一年利息",
                    "expected_output": "30",
                },
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"


def test_sync_evaluate_contract_error_returns_400(api_client):
    response = api_client.post("/api/v1/evaluate", json={"wrong": "data"})
    assert response.status_code == 400
    assert response.json()["code"] == "CONTRACT_ERROR"


def test_sync_evaluate_domain_error_returns_422(api_client):
    response = api_client.post(
        "/api/v1/evaluate",
        json={"id": "x", "type": "unknown_type", "payload": {"a": 1}},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "DOMAIN_ERROR"


def test_async_evaluate_queues_task(api_client, mock_llm):
    with patch("src.workers.tasks._get_evaluation_engine") as mock_engine:
        mock_engine.return_value = MagicMock(run=MagicMock(return_value=MagicMock(
            status=MagicMock(value="passed"),
            latency_ms=100,
        )))

        response = api_client.post(
            "/api/v1/evaluate/async",
            json={
                "id": "async_001",
                "type": "finance",
                "payload": {
                    "user_input": "1000元贷款3%一年利息",
                    "expected_output": "30",
                },
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "queued"
        assert body["case_id"] == "async_001"
        assert body["task_id"]


def test_get_task_status_endpoint(monkeypatch):
    class FakeAsyncResult:
        state = "SUCCESS"

        def ready(self):
            return True

        @property
        def result(self):
            return {"status": "success", "evaluation_status": "passed", "case_id": "x"}

    def mock_get_celery_app():
        mock_app = MagicMock()
        mock_app.AsyncResult = lambda task_id: FakeAsyncResult()
        return mock_app

    monkeypatch.setattr("src.api.server._get_celery_app", mock_get_celery_app)

    client = TestClient(app)

    response = client.get("/api/v1/tasks/fake-task-id")
    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == "fake-task-id"
    assert body["state"] == "SUCCESS"
    assert body["result"]["evaluation_status"] == "passed"


def test_async_evaluate_invalid_payload_returns_400(api_client):
    response = api_client.post("/api/v1/evaluate/async", json={"id": "only_id"})
    assert response.status_code == 400
    assert response.json()["code"] == "CONTRACT_ERROR"


def test_normalize_legacy_payload_format():
    legacy = {
        "id": "legacy_1",
        "type": "general",
        "user_input": "hello",
        "metadata": {"k": "v"},
    }
    normalized = _normalize_raw_data(legacy)
    assert normalized["payload"]["user_input"] == "hello"
    assert normalized["metadata"] == {"k": "v"}


def test_run_evaluation_service_injects_client(mock_llm):
    result = run_evaluation_service(
        {
            "id": "svc_001",
            "type": "general",
            "payload": {
                "user_input": "hello",
            },
        },
        client=mock_llm,
    )
    assert result["status"] == "success"
    mock_llm.chat.assert_called()


def test_create_llm_client_returns_stub_without_api_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    client = create_llm_client()
    assert isinstance(client, StubLLMClient)


def test_create_llm_client_returns_injected_instance(mock_llm):
    assert create_llm_client(client=mock_llm) is mock_llm


def test_health_check_endpoint(api_client):
    response = api_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["service"] == "ai-eval-platform"


def test_metrics_endpoint(api_client):
    response = api_client.get("/metrics")
    assert response.status_code == 200
    assert "evaluation_latency" in response.text.lower() or "buffer_size" in response.text.lower()


def test_test_echo_endpoint(api_client):
    response = api_client.get("/api/v1/test/echo")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"


def test_test_database_endpoint(api_client, monkeypatch):
    from src.infra.db.repository import EvaluationRepository

    original_count = EvaluationRepository.count

    def mock_count(self):
        return 0

    monkeypatch.setattr(EvaluationRepository, 'count', mock_count)

    response = api_client.get("/api/v1/test/db")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"

    monkeypatch.setattr(EvaluationRepository, 'count', original_count)


def test_get_recent_records_endpoint(api_client, monkeypatch):
    from src.infra.db.repository import EvaluationRepository

    def mock_get_recent(self, limit=10):
        return []

    monkeypatch.setattr(EvaluationRepository, 'get_recent', mock_get_recent)

    response = api_client.get("/api/v1/records")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["count"] == 0


def test_get_dashboard_stats_endpoint(api_client, monkeypatch):
    from src.infra.db.repository import EvaluationRepository

    def mock_count(self):
        return 100

    def mock_get_recent(self, limit=5):
        return [{"status": "passed"}, {"status": "failed"}]

    monkeypatch.setattr(EvaluationRepository, 'count', mock_count)
    monkeypatch.setattr(EvaluationRepository, 'get_recent', mock_get_recent)

    response = api_client.get("/api/v1/dashboard/stats")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["data"]["total_records"] == 100


def test_dashboard_endpoint(api_client, monkeypatch):
    from src.infra.db.repository import EvaluationRepository

    def mock_count(self):
        return 0

    def mock_get_recent(self, limit=5):
        return []

    monkeypatch.setattr(EvaluationRepository, 'count', mock_count)
    monkeypatch.setattr(EvaluationRepository, 'get_recent', mock_get_recent)

    response = api_client.get("/")
    assert response.status_code == 200
    assert "AI Eval Platform" in response.text