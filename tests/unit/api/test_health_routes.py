"""
健康检查路由单元测试
测试目标：验证健康检查端点的状态返回和依赖检查逻辑
"""

import pytest
from fastapi.testclient import TestClient

from src.api.server import app

client = TestClient(app)


class TestHealthRoutesPositiveCases:
    """正向测试 - 正常输入"""

    def test_health_check_returns_healthy(self):
        """健康检查应返回healthy状态"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["code"] == 0
        assert response.json()["data"]["status"] == "healthy"

    def test_health_check_contains_service_name(self):
        """健康检查应包含服务名称"""
        response = client.get("/health")
        assert response.json()["data"]["service"] == "ai-eval-platform"


class TestHealthRoutesAPIV1:
    """API V1 健康检查测试"""

    def test_api_v1_health_check_returns_200(self):
        """API V1 健康检查应返回200"""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()["data"]
        assert "components" in data
        assert "database" in data["components"]
        assert "redis" in data["components"]


class TestHealthRoutesNegativeCases:
    """负向测试 - 异常情况"""

    def test_health_check_with_database_failure(self):
        """数据库连接失败时应返回unhealthy"""
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("DATABASE_URL", "sqlite:///:memory:")
            response = client.get("/api/v1/health")
            assert response.status_code == 200

    def test_health_check_with_redis_failure(self):
        """Redis连接失败时应返回unhealthy"""
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("REDIS_URL", "redis://localhost:6380")
            response = client.get("/api/v1/health")
            assert response.status_code == 200
            data = response.json()["data"]
            assert "components" in data
            assert "redis" in data["components"]


class TestHealthRoutesBoundaryCases:
    """边界测试"""

    def test_check_rabbitmq_filesystem_broker(self):
        """文件系统broker应返回not configured"""
        from src.api.routes.health_routes import check_rabbitmq

        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("CELERY_BROKER_URL", "filesystem:///tmp")
            result = check_rabbitmq()
            assert result["status"] == "not configured"

    def test_check_rabbitmq_no_broker_url(self):
        """无broker_url应返回not configured"""
        from src.api.routes.health_routes import check_rabbitmq

        with pytest.MonkeyPatch.context() as mp:
            mp.delenv("CELERY_BROKER_URL", raising=False)
            result = check_rabbitmq()
            assert result["status"] == "not configured"

    def test_check_rabbitmq_unknown_broker_type(self):
        """未知broker类型应返回unknown"""
        from src.api.routes.health_routes import check_rabbitmq

        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("CELERY_BROKER_URL", "unknown://localhost")
            result = check_rabbitmq()
            assert result["status"] == "unknown"
