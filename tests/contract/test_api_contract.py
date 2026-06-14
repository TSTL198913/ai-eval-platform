"""API 契约：OpenAPI 与 HTTP 语义与 EvaluationSchema 对齐。"""

import pytest
from fastapi.testclient import TestClient

from src.api.server import app

pytestmark = pytest.mark.contract


@pytest.fixture
def client():
    return TestClient(app)


def test_openapi_contains_core_endpoints(client):
    schema = app.openapi()
    paths = schema.get("paths", {})

    assert "/api/v1/evaluate" in paths
    assert "post" in paths["/api/v1/evaluate"]
    assert "/api/v1/evaluate/async" in paths
    assert "post" in paths["/api/v1/evaluate/async"]
    assert "/api/v1/tasks/{task_id}" in paths
    assert "get" in paths["/api/v1/tasks/{task_id}"]


def test_openapi_evaluate_request_accepts_object_body(client):
    schema = app.openapi()
    post_op = schema["paths"]["/api/v1/evaluate"]["post"]
    request_body = post_op.get("requestBody", {})
    content = request_body.get("content", {})

    # FastAPI 对 dict 参数可能生成 object schema 或留空；至少应接受 JSON body
    assert "application/json" in content or request_body == {}


def test_sync_evaluate_response_contract(client, monkeypatch, mock_llm):
    monkeypatch.setattr(
        "src.services.evaluator_svc.create_llm_client",
        lambda client=None: mock_llm,
    )
    mock_llm.chat.return_value = "利息为30元。"

    response = client.post(
        "/api/v1/evaluate",
        json={
            "id": "contract_001",
            "type": "finance",
            "payload": {
                "user_input": "1000元3%利息",
                "expected_output": "30",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert "record_id" in body
    assert "evaluation_status" in body
    assert "latency_ms" in body
    assert "data" in body


def test_async_evaluate_response_contract(client, monkeypatch, mock_llm):
    monkeypatch.setattr(
        "src.workers.tasks.create_llm_client",
        lambda client=None: mock_llm,
    )
    mock_llm.chat.return_value = "利息为30元。"

    response = client.post(
        "/api/v1/evaluate/async",
        json={
            "id": "contract_async",
            "type": "finance",
            "payload": {
                "user_input": "利息",
                "expected_output": "30",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"
    assert "task_id" in body
    assert body["case_id"] == "contract_async"


def test_contract_error_response_shape(client):
    response = client.post("/api/v1/evaluate", json={"invalid": True})
    assert response.status_code == 400
    body = response.json()
    assert body["status"] == "error"
    assert body["code"] == "CONTRACT_ERROR"
    assert "message" in body
