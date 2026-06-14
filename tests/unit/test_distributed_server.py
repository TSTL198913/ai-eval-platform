"""
分布式服务器测试用例
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.distributed_server import app


@pytest.fixture(autouse=True)
def mock_redis_and_rate_limiter():
    """全局 Mock Redis 和限流器，避免测试依赖真实 Redis"""
    with patch("src.api.distributed_server.get_redis") as mock_get_redis:
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.info.return_value = {"redis_version": "7.0.0", "connected_clients": 1}
        mock_get_redis.return_value = mock_redis

        with patch("src.api.distributed_server.get_rate_limiter") as mock_get_rate_limiter:
            mock_result = MagicMock()
            mock_result.retry_after_ms = 0
            mock_result.remaining_tokens = 99
            mock_limiter = MagicMock()
            mock_limiter.is_allowed.return_value = (True, mock_result)
            mock_get_rate_limiter.return_value = mock_limiter

            # 清除缓存的客户端
            import src.api.distributed_server as server

            server._redis_client = None
            server._rate_limiter = None

            yield


class TestHealthEndpoints:
    """测试健康检查端点"""

    def test_health_check(self):
        """测试 /health 端点"""
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert data["status"] == "healthy"
            assert "service" in data
            assert "version" in data
            assert "timestamp" in data

    def test_liveness_check(self):
        """测试 /health/live 端点"""
        with TestClient(app) as client:
            response = client.get("/health/live")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "alive"
            assert "timestamp" in data

    def test_health_check_has_trace_id_header(self):
        """测试健康检查响应包含 X-Trace-ID 头"""
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            assert "X-Trace-ID" in response.headers


class TestMetricsEndpoints:
    """测试指标端点"""

    def test_metrics_endpoint(self):
        """测试 /metrics 端点"""
        with TestClient(app) as client:
            response = client.get("/metrics")
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/plain; charset=utf-8"

    def test_metrics_json_endpoint(self):
        """测试 /metrics/json 端点"""
        with TestClient(app) as client:
            response = client.get("/metrics/json")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)


class TestRateLimitMiddleware:
    """测试限流中间件"""

    def test_rate_limit_exceeded(self):
        """测试限流超过时返回 429"""
        with patch("src.api.distributed_server.get_rate_limiter") as mock_rate_limiter:
            mock_result = MagicMock()
            mock_result.retry_after_ms = 10000
            mock_result.remaining_tokens = 0
            mock_rate_limiter.return_value.is_allowed.return_value = (False, mock_result)

            with TestClient(app) as client:
                response = client.post("/api/v1/evaluate", json={"case_id": "test"})
                assert response.status_code == 429
                data = response.json()
                assert data["error"] == "rate_limit_exceeded"
                assert "Retry-After" in response.headers
                assert "X-RateLimit-Remaining" in response.headers

    def test_rate_limit_allowed(self):
        """测试限流允许时正常处理"""
        with patch("src.api.distributed_server.get_rate_limiter") as mock_rate_limiter:
            mock_result = MagicMock()
            mock_result.retry_after_ms = 0
            mock_result.remaining_tokens = 99
            mock_rate_limiter.return_value.is_allowed.return_value = (True, mock_result)

            with TestClient(app) as client:
                response = client.post("/api/v1/evaluate", json={"case_id": "test"})
                assert response.status_code == 200
                assert "X-RateLimit-Remaining" in response.headers


class TestEvaluateEndpoints:
    """测试评测端点"""

    def test_evaluate_sync(self):
        """测试同步评测接口"""
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/evaluate",
                json={"case_id": "test_case_001", "domain": "general"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["case_id"] == "test_case_001"
            assert "trace_id" in data

    def test_evaluate_sync_missing_case_id(self):
        """测试同步评测缺少 case_id"""
        with TestClient(app) as client:
            response = client.post("/api/v1/evaluate", json={"domain": "general"})
            assert response.status_code == 200
            data = response.json()
            assert data["case_id"] is None

    def test_evaluate_async(self):
        """测试异步评测接口"""
        with patch("src.api.distributed_server.eval_case_task") as mock_task:
            mock_task.delay.return_value.id = "test-task-id-123"

            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/evaluate/async",
                    json={"case_id": "test_case_002", "domain": "general"},
                )
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "queued"
                assert data["task_id"] == "test-task-id-123"
                assert data["case_id"] == "test_case_002"
                assert "X-Trace-ID" in response.headers
                assert "X-Task-ID" in response.headers

    def test_evaluate_async_no_case_id(self):
        """测试异步评测没有 case_id 时自动生成"""
        with patch("src.api.distributed_server.eval_case_task") as mock_task:
            mock_task.delay.return_value.id = "test-task-id-456"

            with TestClient(app) as client:
                response = client.post("/api/v1/evaluate/async", json={"domain": "general"})
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "queued"
                assert data["case_id"].startswith("case_")


class TestTaskEndpoints:
    """测试任务查询端点"""

    def test_get_task_status(self):
        """测试查询任务状态"""
        with patch("src.api.distributed_server.celery_app") as mock_celery:
            mock_result = MagicMock()
            mock_result.state = "PENDING"
            mock_result.ready.return_value = False
            mock_celery.AsyncResult.return_value = mock_result

            with TestClient(app) as client:
                response = client.get("/api/v1/tasks/test-task-id")
                assert response.status_code == 200
                data = response.json()
                assert data["task_id"] == "test-task-id"
                assert data["state"] == "PENDING"
                assert data["result"] is None

    def test_get_task_status_completed(self):
        """测试查询已完成任务状态"""
        with patch("src.api.distributed_server.celery_app") as mock_celery:
            mock_result = MagicMock()
            mock_result.state = "SUCCESS"
            mock_result.ready.return_value = True
            mock_result.result = {"score": 0.9}
            mock_celery.AsyncResult.return_value = mock_result

            with TestClient(app) as client:
                response = client.get("/api/v1/tasks/test-task-id")
                assert response.status_code == 200
                data = response.json()
                assert data["state"] == "SUCCESS"
                assert data["result"] == {"score": 0.9}

    def test_get_task_result_ready(self):
        """测试获取已完成任务结果"""
        with patch("src.api.distributed_server.celery_app") as mock_celery:
            mock_result = MagicMock()
            mock_result.ready.return_value = True
            mock_result.result = {"score": 0.85, "is_valid": True}
            mock_celery.AsyncResult.return_value = mock_result

            with TestClient(app) as client:
                response = client.get("/api/v1/tasks/test-task-id/result")
                assert response.status_code == 200
                assert response.json() == {"score": 0.85, "is_valid": True}

    def test_get_task_result_not_ready(self):
        """测试获取未完成任务结果返回 404"""
        with patch("src.api.distributed_server.celery_app") as mock_celery:
            mock_result = MagicMock()
            mock_result.ready.return_value = False
            mock_celery.AsyncResult.return_value = mock_result

            with TestClient(app) as client:
                response = client.get("/api/v1/tasks/test-task-id/result")
                assert response.status_code == 404


class TestReadinessCheck:
    """测试就绪检查端点"""

    def test_readiness_check_with_mocked_dependencies(self):
        """测试就绪检查使用 mock 的依赖"""
        with TestClient(app) as client:
            response = client.get("/health/ready")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "checks" in data

    def test_detailed_health(self):
        """测试详细健康检查"""
        with TestClient(app) as client:
            response = client.get("/health/detailed")
            assert response.status_code == 200
            data = response.json()
            assert "service" in data
            assert "components" in data
            assert "timestamp" in data
