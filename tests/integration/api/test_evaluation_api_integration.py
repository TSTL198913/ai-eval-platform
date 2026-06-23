"""
评估API集成测试
测试目标：验证API层与Service层的完整集成流程
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.routes.evaluation_routes import _sync_task_results
from src.api.server import app


@pytest.fixture
def client():
    """FastAPI测试客户端"""
    return TestClient(app)


@pytest.fixture
def mock_evaluator_service():
    """Mock评估服务"""
    with patch("src.api.routes.evaluation_routes.run_evaluation_service") as mock:
        mock.return_value = {
            "status": "success",
            "record_id": "test-001",
            "evaluation_status": "passed",
            "data": {"is_valid": True, "score": 0.9},
            "persist": True,
        }
        yield mock


@pytest.fixture(autouse=True)
def mock_idempotency_checker():
    """Mock幂等性检查器（自动应用）"""
    with patch("src.api.routes.evaluation_routes._get_idempotency_checker") as mock:
        checker = MagicMock()
        checker.get_cached_result.return_value = None
        checker.mark_processing.return_value = True
        checker.mark_processed.return_value = None
        checker.clear.return_value = None
        mock.return_value = checker
        yield checker


class TestEvaluateEndpoint:
    """评估端点测试"""

    def test_evaluate_endpoint_success(self, client, mock_evaluator_service):
        """评估端点应成功返回评估结果"""
        response = client.post(
            "/api/v1/evaluate",
            json={
                "id": "eval-001",
                "type": "semantic",
                "payload": {
                    "actual_output": "测试输出",
                    "expected_output": "期望输出",
                },
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["status"] == "success"
        assert data["data"]["evaluation_status"] == "passed"
        mock_evaluator_service.assert_called_once()

    def test_evaluate_endpoint_with_model_provider(self, client, mock_evaluator_service):
        """评估端点应支持指定模型提供者"""
        response = client.post(
            "/api/v1/evaluate",
            json={
                "id": "unique-model-provider-id",
                "type": "semantic",
                "model_provider": "deepseek",
                "model_name": "deepseek-chat",
                "payload": {
                    "actual_output": "测试输出",
                    "expected_output": "期望输出",
                },
            },
        )

        assert response.status_code == 200
        mock_evaluator_service.assert_called_once()
        call_kwargs = mock_evaluator_service.call_args[0][0]
        assert call_kwargs["model_provider"] == "deepseek"
        assert call_kwargs["model_name"] == "deepseek-chat"

    def test_evaluate_endpoint_validation_error(self, client):
        """评估端点应返回验证错误"""
        with patch("src.api.routes.evaluation_routes.run_evaluation_service") as mock:
            mock.return_value = {
                "status": "error",
                "code": "CONTRACT_ERROR",
                "message": "Invalid payload",
            }

            response = client.post(
                "/api/v1/evaluate",
                json={"id": "eval-003", "type": "semantic", "payload": {}},
            )

            assert response.status_code == 400
            data = response.json()
            assert data["code"] == "CONTRACT_ERROR"

    def test_evaluate_endpoint_idempotency_cached_result(self, client, mock_idempotency_checker):
        """幂等性检查应返回缓存结果"""
        cached_result = {
            "status": "success",
            "record_id": "eval-004",
            "evaluation_status": "passed",
        }
        mock_idempotency_checker.get_cached_result.return_value = cached_result

        with patch("src.api.routes.evaluation_routes.run_evaluation_service") as mock:
            response = client.post(
                "/api/v1/evaluate",
                json={
                    "id": "eval-004",
                    "type": "semantic",
                    "payload": {"actual_output": "测试"},
                },
            )

            assert response.status_code == 200
            mock.assert_not_called()

    def test_evaluate_endpoint_idempotency_conflict(self, client, mock_idempotency_checker):
        """幂等性检查应返回冲突状态"""
        mock_idempotency_checker.mark_processing.return_value = False

        response = client.post(
            "/api/v1/evaluate",
            json={
                "id": "eval-005",
                "type": "semantic",
                "payload": {"actual_output": "测试"},
            },
        )

        assert response.status_code == 409
        data = response.json()
        assert "请求正在处理中" in data["message"]

    def test_evaluate_endpoint_without_id(self, client, mock_evaluator_service):
        """评估端点应支持无id请求"""
        response = client.post(
            "/api/v1/evaluate",
            json={
                "type": "semantic",
                "payload": {"actual_output": "测试", "expected_output": "测试"},
            },
        )

        assert response.status_code == 200


class TestEvaluateAsyncEndpoint:
    """异步评估端点测试"""

    def test_evaluate_async_endpoint_success(self, client):
        """异步评估端点应返回任务ID"""
        with patch("src.api.routes.evaluation_routes._get_eval_case_task") as mock_task:
            mock_instance = MagicMock()
            mock_instance.delay.return_value.id = "task-abc123"
            mock_task.return_value = mock_instance

            response = client.post(
                "/api/v1/evaluate/async",
                json={
                    "id": "async-001",
                    "type": "semantic",
                    "payload": {"actual_output": "测试", "expected_output": "测试"},
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert data["data"]["task_id"] == "task-abc123"
            assert data["data"]["case_id"] == "async-001"
            assert data["data"]["status"] == "queued"

    def test_evaluate_async_endpoint_celery_fallback(self, client):
        """Celery失败时应降级为同步执行"""
        with patch("src.api.routes.evaluation_routes._get_eval_case_task") as mock_task:
            mock_task.side_effect = Exception("Celery not available")

            with patch("src.api.routes.evaluation_routes.run_evaluation_service") as mock_service:
                mock_service.return_value = {
                    "status": "success",
                    "record_id": "async-002",
                    "evaluation_status": "passed",
                }

                response = client.post(
                    "/api/v1/evaluate/async",
                    json={
                        "id": "async-002",
                        "type": "semantic",
                        "payload": {"actual_output": "测试"},
                    },
                )

                assert response.status_code == 200
                data = response.json()
                assert data["data"]["status"] == "completed"
                assert data["data"]["task_id"].startswith("sync-")

    def test_evaluate_async_endpoint_validation_error(self, client):
        """异步评估端点应返回验证错误"""
        response = client.post(
            "/api/v1/evaluate/async",
            json={"invalid": "data"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "输入数据校验失败" in data["message"]


class TestGetTaskStatusEndpoint:
    """任务状态查询端点测试"""

    def test_get_task_status_sync_task(self, client):
        """应返回同步任务状态"""
        _sync_task_results["sync-test-001"] = {
            "status": "success",
            "record_id": "test-001",
        }

        response = client.get("/api/v1/tasks/sync-test-001")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["status"] == "completed"
        assert data["data"]["task_id"] == "sync-test-001"

    def test_get_task_status_sync_task_not_found(self, client):
        """应返回同步任务未找到"""
        response = client.get("/api/v1/tasks/sync-nonexistent")

        assert response.status_code == 404
        data = response.json()
        assert "Task not found" in data["message"]

    def test_get_task_status_test_task(self, client):
        """应返回测试任务状态"""
        response = client.get("/api/v1/tasks/test-task-001")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["status"] == "completed"

    def test_get_task_status_celery_pending(self, client):
        """应返回Celery待处理任务状态（无Celery时返回pending）"""
        response = client.get("/api/v1/tasks/celery-abc123")
        assert response.status_code == 200

    def test_get_task_status_celery_completed(self, client):
        """应返回Celery完成任务状态（无Celery时返回pending）"""
        response = client.get("/api/v1/tasks/celery-abc123")
        assert response.status_code == 200


class TestBatchEvaluateEndpoint:
    """批量评估端点测试"""

    def test_batch_evaluate_endpoint_success(self, client):
        """批量评估端点应成功处理多个评估任务"""
        with patch("src.api.routes.evaluation_routes.run_evaluation_service") as mock_service:
            mock_service.return_value = {
                "status": "success",
                "record_id": "batch-001",
                "evaluation_status": "passed",
            }

            response = client.post(
                "/api/v1/evaluate/sync-batch",
                json={
                    "cases": [
                        {
                            "id": "batch-001",
                            "type": "semantic",
                            "payload": {"actual_output": "测试1", "expected_output": "期望1"},
                        },
                        {
                            "id": "batch-002",
                            "type": "grammar",
                            "payload": {"actual_output": "正确的句子。"},
                        },
                        {
                            "id": "batch-003",
                            "type": "text",
                            "payload": {"actual_output": "匹配", "expected_output": "匹配"},
                        },
                    ]
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert data["data"]["total"] == 3
            assert len(data["data"]["results"]) == 3
            assert mock_service.call_count == 3

    def test_batch_evaluate_endpoint_empty_cases(self, client):
        """批量评估端点应处理空列表"""
        response = client.post(
            "/api/v1/evaluate/sync-batch",
            json={"cases": []},
        )

        assert response.status_code == 400
        data = response.json()
        assert "cases must be a non-empty list" in data["message"]

    def test_batch_evaluate_endpoint_invalid_cases(self, client):
        """批量评估端点应处理无效数据"""
        with patch("src.api.routes.evaluation_routes.run_evaluation_service") as mock_service:
            mock_service.side_effect = [
                {"status": "success", "record_id": "batch-001"},
                Exception("Internal error"),
                {"status": "success", "record_id": "batch-003"},
            ]

            response = client.post(
                "/api/v1/evaluate/sync-batch",
                json={
                    "cases": [
                        {
                            "id": "batch-001",
                            "type": "semantic",
                            "payload": {"actual_output": "测试"},
                        },
                        {"id": "batch-002", "type": "invalid"},
                        {"id": "batch-003", "type": "text", "payload": {"actual_output": "测试"}},
                    ]
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["data"]["total"] == 3
            assert data["data"]["results"][1]["status"] == "error"
            assert data["data"]["results"][1]["code"] == "INTERNAL_ERROR"


class TestAPIIntegrationWithDataContract:
    """API与数据契约集成测试"""

    def test_api_accepts_standard_payload(self, client, mock_evaluator_service):
        """API应接受标准数据契约"""
        response = client.post(
            "/api/v1/evaluate",
            json={
                "id": "unique-standard-payload-id",
                "type": "semantic",
                "payload": {
                    "prompt": "用户原始问题",
                    "actual_output": "大模型的实际回答",
                    "expected_output": "黄金标准/参考答案",
                },
            },
        )

        assert response.status_code == 200
        mock_evaluator_service.assert_called_once()
        call_kwargs = mock_evaluator_service.call_args[0][0]
        assert "payload" in call_kwargs
        assert call_kwargs["payload"]["prompt"] == "用户原始问题"
        assert call_kwargs["payload"]["actual_output"] == "大模型的实际回答"
        assert call_kwargs["payload"]["expected_output"] == "黄金标准/参考答案"

    def test_api_normalizes_flat_structure(self, client, mock_evaluator_service):
        """API应规范化payload结构"""
        response = client.post(
            "/api/v1/evaluate",
            json={
                "id": "unique-normalize-id",
                "type": "semantic",
                "payload": {
                    "prompt": "测试问题",
                    "actual_output": "实际回答",
                    "expected_output": "期望回答",
                },
            },
        )

        assert response.status_code == 200
        mock_evaluator_service.assert_called_once()
        call_kwargs = mock_evaluator_service.call_args[0][0]
        assert "payload" in call_kwargs
        assert call_kwargs["payload"]["prompt"] == "测试问题"

    def test_api_supports_online_mode(self, client, mock_evaluator_service):
        """API应支持在线模式（无actual_output）"""
        response = client.post(
            "/api/v1/evaluate",
            json={
                "id": "unique-online-mode-id",
                "type": "semantic",
                "payload": {
                    "prompt": "如何重置密码？",
                    "expected_output": "点击设置重置密码",
                },
            },
        )

        assert response.status_code == 200
        mock_evaluator_service.assert_called_once()

    def test_api_supports_offline_mode(self, client, mock_evaluator_service):
        """API应支持离线模式（有actual_output）"""
        response = client.post(
            "/api/v1/evaluate",
            json={
                "id": "unique-offline-mode-id",
                "type": "semantic",
                "payload": {
                    "actual_output": "已有的实际回答",
                    "expected_output": "期望输出",
                },
            },
        )

        assert response.status_code == 200
        mock_evaluator_service.assert_called_once()


class TestAPIErrorHandling:
    """API异常处理测试"""

    def test_api_handles_internal_error(self, client, mock_idempotency_checker):
        """API应处理内部错误"""
        with patch("src.api.routes.evaluation_routes.run_evaluation_service") as mock_service:
            mock_service.return_value = {
                "status": "error",
                "code": "INTERNAL_ERROR",
                "message": "Unexpected error",
            }

            response = client.post(
                "/api/v1/evaluate",
                json={
                    "id": "error-001",
                    "type": "semantic",
                    "payload": {"actual_output": "测试"},
                },
            )

            assert response.status_code == 422
            data = response.json()
            assert data["code"] == "INTERNAL_ERROR"

    def test_api_handles_unknown_evaluator(self, client, mock_idempotency_checker):
        """API应处理未知评估器类型"""
        with patch("src.api.routes.evaluation_routes.run_evaluation_service") as mock_service:
            mock_service.return_value = {
                "status": "error",
                "code": "E2005",
                "message": "Evaluator not found",
            }

            response = client.post(
                "/api/v1/evaluate",
                json={
                    "id": "error-002",
                    "type": "unknown_type",
                    "payload": {"actual_output": "测试"},
                },
            )

            assert response.status_code == 422

    def test_api_handles_empty_payload(self, client):
        """API应处理空payload"""
        with patch("src.api.routes.evaluation_routes.run_evaluation_service") as mock_service:
            mock_service.return_value = {
                "status": "success",
                "evaluation_status": "failed",
                "data": {"is_valid": False},
            }

            response = client.post(
                "/api/v1/evaluate",
                json={"id": "error-003", "type": "semantic", "payload": {}},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["data"]["evaluation_status"] == "failed"
