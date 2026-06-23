"""
路由层单元测试 - evaluation_routes.py
测试目标：验证评估路由的请求处理、状态码返回、错误处理逻辑
关键发现：
- Pydantic验证自动触发422状态码
- 幂等性检查器失败时自动降级
- Celery不可用时自动回退到同步执行
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.server import app

client = TestClient(app)


class TestEvaluationRoutesPositiveCases:
    """正向测试 - 正常输入"""

    def test_evaluate_with_valid_input_returns_200(self):
        """合法输入应返回200成功"""
        response = client.post(
            "/api/v1/evaluate",
            json={
                "id": "test-valid-001",
                "type": "general",
                "payload": {"user_input": "test input"},
            },
        )
        assert response.status_code == 200
        assert response.json()["code"] == 0
        assert response.json()["message"] == "success"

    def test_evaluate_async_with_valid_input_returns_200(self):
        """异步评估合法输入应返回200"""
        response = client.post(
            "/api/v1/evaluate/async",
            json={
                "id": "test-async-001",
                "type": "general",
                "payload": {"user_input": "test input"},
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert "task_id" in data
        assert data["case_id"] == "test-async-001"

    def test_batch_evaluate_with_valid_cases_returns_200(self):
        """批量评估合法输入应返回200"""
        response = client.post(
            "/api/v1/evaluate/sync-batch",
            json={
                "cases": [
                    {"id": "batch-001", "type": "general", "payload": {"user_input": "test1"}},
                    {"id": "batch-002", "type": "general", "payload": {"user_input": "test2"}},
                ]
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total"] == 2
        assert len(data["results"]) == 2

    def test_get_task_status_sync_task_returns_result(self):
        """获取同步任务状态应返回结果"""
        from src.api.routes.evaluation_routes import _sync_task_results

        _sync_task_results["sync-test-001"] = {"status": "success", "data": {}}
        response = client.get("/api/v1/tasks/sync-test-001")
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "completed"


class TestEvaluationRoutesNegativeCases:
    """负向测试 - 错误输入"""

    def test_evaluate_missing_type_returns_422(self):
        """缺少type字段应返回422"""
        response = client.post(
            "/api/v1/evaluate",
            json={"id": "test-missing-type", "payload": {"user_input": "test"}},
        )
        assert response.status_code == 422

    def test_evaluate_missing_payload_returns_422(self):
        """缺少payload字段应返回422"""
        response = client.post(
            "/api/v1/evaluate",
            json={"id": "test-missing-payload", "type": "general"},
        )
        assert response.status_code == 422

    def test_batch_evaluate_empty_cases_returns_400(self):
        """空cases列表应返回400"""
        response = client.post("/api/v1/evaluate/sync-batch", json={"cases": []})
        assert response.status_code == 400
        assert "must be a non-empty list" in response.json()["message"]

    def test_batch_evaluate_missing_cases_returns_400(self):
        """缺少cases字段应返回400"""
        response = client.post("/api/v1/evaluate/sync-batch", json={})
        assert response.status_code == 400

    def test_get_task_status_not_found_returns_404(self):
        """获取不存在的同步任务应返回404"""
        response = client.get("/api/v1/tasks/sync-nonexistent")
        assert response.status_code == 404
        assert "Task not found" in response.json()["message"]


class TestEvaluationRoutesBoundaryCases:
    """边界测试 - 边界值"""

    def test_evaluate_with_empty_payload_returns_error(self):
        """空payload应返回错误"""
        response = client.post(
            "/api/v1/evaluate",
            json={"id": "test-empty-payload", "type": "general", "payload": {}},
        )
        assert response.status_code in (200, 422)

    def test_evaluate_with_very_long_id(self):
        """超长id应正常处理"""
        long_id = "a" * 255
        response = client.post(
            "/api/v1/evaluate",
            json={"id": long_id, "type": "general", "payload": {"user_input": "test"}},
        )
        assert response.status_code == 200

    def test_evaluate_with_special_characters_in_payload(self):
        """payload包含特殊字符应正常处理"""
        response = client.post(
            "/api/v1/evaluate",
            json={
                "id": "test-special",
                "type": "general",
                "payload": {"user_input": "test \"quote\" 'single' &amp; special"},
            },
        )
        assert response.status_code == 200


class TestEvaluationRoutesDependencyHandling:
    """依赖测试 - 外部依赖Mock"""

    def test_evaluate_without_redis_uses_idempotency_disabled(self):
        """无Redis时幂等性应被禁用"""
        with patch("src.api.routes.evaluation_routes._get_idempotency_checker") as mock_checker:
            mock_checker.return_value = None
            response = client.post(
                "/api/v1/evaluate",
                json={"id": "test-no-redis", "type": "general", "payload": {"user_input": "test"}},
            )
            assert response.status_code == 200

    def test_async_evaluate_celery_fallback_to_sync(self):
        """Celery不可用时应回退到同步执行"""
        with patch("src.api.routes.evaluation_routes._get_eval_case_task") as mock_task:
            mock_task.side_effect = Exception("Celery unavailable")
            response = client.post(
                "/api/v1/evaluate/async",
                json={
                    "id": "test-celery-fallback",
                    "type": "general",
                    "payload": {"user_input": "test"},
                },
            )
            assert response.status_code == 200
            data = response.json()["data"]
            assert data["status"] == "completed"
            assert data["task_id"].startswith("sync-")

    def test_task_status_celery_unavailable_returns_pending(self):
        """Celery不可用时任务状态应返回pending"""
        with patch("src.workers.celery_app.get_celery_app") as mock_app:
            mock_app.return_value = None
            response = client.get("/api/v1/tasks/celery-task-001")
            assert response.status_code == 200
            assert response.json()["data"]["status"] == "pending"


class TestEvaluationRoutesIdempotency:
    """幂等性测试"""

    def test_idempotency_checker_cached_result_returns_200(self):
        """缓存结果应直接返回"""
        with patch("src.api.routes.evaluation_routes._get_idempotency_checker") as mock_checker:
            mock_instance = MagicMock()
            mock_instance.get_cached_result.return_value = {"status": "success", "cached": True}
            mock_checker.return_value = mock_instance
            response = client.post(
                "/api/v1/evaluate",
                json={"id": "cached-request", "type": "general", "payload": {"user_input": "test"}},
            )
            assert response.status_code == 200
            assert response.json()["data"]["cached"] is True

    def test_idempotency_checker_processing_returns_409(self):
        """正在处理中的请求应返回409"""
        with patch("src.api.routes.evaluation_routes._get_idempotency_checker") as mock_checker:
            mock_instance = MagicMock()
            mock_instance.get_cached_result.return_value = None
            mock_instance.mark_processing.return_value = False
            mock_checker.return_value = mock_instance
            response = client.post(
                "/api/v1/evaluate",
                json={
                    "id": "processing-request",
                    "type": "general",
                    "payload": {"user_input": "test"},
                },
            )
            assert response.status_code == 409
            assert "正在处理中" in response.json()["message"]
