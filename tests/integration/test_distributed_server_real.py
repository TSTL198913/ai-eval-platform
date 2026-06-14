"""
分布式服务器集成测试 - 使用真实 Redis 连接
需要先启动 Redis 服务: D:\\softwore\\Redis-x64-5.0.14.1\redis-server.exe
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.distributed_server import app


@pytest.fixture(autouse=True)
def use_real_redis():
    """清除全局缓存，确保使用真实 Redis 连接"""
    import src.api.distributed_server as server

    server._redis_client = None
    server._rate_limiter = None
    yield
    # 测试后清理
    server._redis_client = None
    server._rate_limiter = None


class TestHealthEndpointsRealRedis:
    """使用真实 Redis 的健康检查端点测试"""

    def test_health_check_with_real_redis(self):
        """测试 /health 端点使用真实 Redis"""
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert "service" in data
            assert "version" in data

    def test_liveness_check(self):
        """测试 /health/live 端点"""
        with TestClient(app) as client:
            response = client.get("/health/live")
            assert response.status_code == 200
            assert response.json()["status"] == "alive"

    def test_health_check_trace_id_header(self):
        """测试健康检查包含追踪 ID"""
        with TestClient(app) as client:
            response = client.get("/health")
            assert "X-Trace-ID" in response.headers


class TestReadinessCheckRealRedis:
    """使用真实 Redis 的就绪检查测试"""

    def test_readiness_check_redis_and_database(self):
        """测试就绪检查 - Redis 和数据库"""
        with TestClient(app) as client:
            response = client.get("/health/ready")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "checks" in data
            # Redis 应该连接成功
            assert data["checks"]["redis"] is True
            # 数据库应该连接成功
            assert data["checks"]["database"] is True

    def test_detailed_health_with_redis_info(self):
        """测试详细健康检查包含 Redis 信息"""
        with TestClient(app) as client:
            response = client.get("/health/detailed")
            assert response.status_code == 200
            data = response.json()
            assert data["components"]["redis"]["status"] == "healthy"
            assert "version" in data["components"]["redis"]


class TestRateLimitWithRealRedis:
    """使用真实 Redis 的限流测试"""

    def test_rate_limit_allows_normal_request(self):
        """测试限流允许正常请求"""
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/evaluate",
                json={"case_id": "rate_limit_test_001"},
            )
            assert response.status_code == 200
            # 注意：当 is_allowed 返回 True 但 result 为 None 时，不添加限流头
            # 这是限流器的预期行为

    def test_rate_limit_returns_200(self):
        """测试限流对正常请求返回 200"""
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200


class TestEvaluateWithRealRedis:
    """使用真实 Redis 的评测端点测试"""

    def test_evaluate_sync(self):
        """测试同步评测接口"""
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/evaluate",
                json={"case_id": "real_redis_test_001", "domain": "general"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["case_id"] == "real_redis_test_001"

    def test_evaluate_async(self):
        """测试异步评测接口"""
        with patch("src.api.distributed_server.eval_case_task") as mock_task:
            mock_task.delay.return_value.id = "real-redis-task-id"
            mock_task.delay.return_value.state = "PENDING"

            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/evaluate/async",
                    json={"case_id": "real_redis_test_002", "domain": "general"},
                )
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "queued"


class TestMetricsWithRealRedis:
    """使用真实 Redis 的指标端点测试"""

    def test_metrics_endpoint(self):
        """测试 Prometheus 指标端点"""
        with TestClient(app) as client:
            response = client.get("/metrics")
            assert response.status_code == 200
            assert "text/plain" in response.headers["content-type"]

    def test_metrics_json_endpoint(self):
        """测试 JSON 指标端点"""
        with TestClient(app) as client:
            response = client.get("/metrics/json")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)


class TestTaskEndpointsWithRealRedis:
    """使用真实 Redis 的任务端点测试"""

    def test_task_status_mocked_celery(self):
        """测试任务状态查询（Celery 使用 Mock）"""
        with patch("src.api.distributed_server.celery_app") as mock_celery:
            mock_result = MagicMock()
            mock_result.state = "PENDING"
            mock_result.ready.return_value = False
            mock_celery.AsyncResult.return_value = mock_result

            with TestClient(app) as client:
                response = client.get("/api/v1/tasks/redis-test-task-id")
                assert response.status_code == 200
                assert response.json()["task_id"] == "redis-test-task-id"

    def test_task_result_not_ready(self):
        """测试获取未完成任务结果"""
        with patch("src.api.distributed_server.celery_app") as mock_celery:
            mock_result = MagicMock()
            mock_result.ready.return_value = False
            mock_celery.AsyncResult.return_value = mock_result

            with TestClient(app) as client:
                response = client.get("/api/v1/tasks/redis-test-task-id/result")
                assert response.status_code == 404
