import pytest
from fastapi.testclient import TestClient

from src.api.server import app
from src.domain.models.llm_factory import create_llm_client
from src.domain.models.stub import StubLLMClient
from src.services.evaluator_svc import _normalize_raw_data, run_evaluation_service


@pytest.fixture
def api_client():
    return TestClient(app)


def test_sync_evaluate_success(api_client, monkeypatch, mock_llm):
    monkeypatch.setattr(
        "src.services.evaluator_svc.create_llm_client",
        lambda client=None: mock_llm,
    )

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
    assert body["record_id"] == "api_001"
    assert body["evaluation_status"] == "passed"
    assert body["latency_ms"] >= 0


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


def test_async_evaluate_queues_task(api_client, monkeypatch, mock_llm):
    mock_llm.chat.return_value = "利息为30元，本金1000元。"
    monkeypatch.setattr(
        "src.workers.tasks.create_llm_client",
        lambda client=None: mock_llm,
    )

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

    monkeypatch.setattr(
        "src.api.server.celery_app.AsyncResult",
        lambda task_id: FakeAsyncResult(),
    )
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
            "type": "finance",
            "payload": {
                "user_input": "计算利息",
                "expected_output": "30",
            },
        },
        client=mock_llm,
    )
    assert result["status"] == "success"
    assert result["evaluation_status"] == "passed"
    mock_llm.chat.assert_called_once()


def test_create_llm_client_returns_stub_without_api_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    client = create_llm_client()
    assert isinstance(client, StubLLMClient)


def test_create_llm_client_returns_injected_instance(mock_llm):
    assert create_llm_client(mock_llm) is mock_llm
