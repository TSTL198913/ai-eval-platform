"""
健康检查部署测试 - 验证API服务健康状态
场景覆盖: H-001, H-002, H-003, H-004
"""

import time

import pytest
import requests


@pytest.mark.health
class TestHealthCheck:
    """健康检查测试"""

    def test_basic_health_endpoint(self, api_url):
        """场景H-001: 基础健康检查端点"""
        start_time = time.time()
        response = requests.get(f"{api_url}/health", timeout=10)
        elapsed = time.time() - start_time

        assert response.status_code == 200, f"健康检查失败: {response.status_code}"
        data = response.json()
        assert data["code"] == 0, f"响应code错误: {data.get('code')}"
        assert data["message"] == "success", f"响应message错误: {data.get('message')}"
        assert data["data"]["status"] == "healthy", f"服务状态不健康: {data['data'].get('status')}"
        assert elapsed < 5, f"健康检查响应超时: {elapsed:.2f}s"

    def test_detailed_health_endpoint(self, api_url):
        """场景H-002: 详细健康检查端点"""
        response = requests.get(f"{api_url}/api/v1/health", timeout=15)

        assert response.status_code == 200, f"详细健康检查失败: {response.status_code}"
        data = response.json()
        assert data["code"] == 0, f"响应code错误: {data.get('code')}"
        assert "components" in data["data"], "缺少components字段"

        components = data["data"]["components"]
        assert "database" in components, "缺少database组件状态"
        assert "redis" in components, "缺少redis组件状态"
        assert "rabbitmq" in components, "缺少rabbitmq组件状态"

    def test_root_endpoint(self, api_url):
        """场景H-003: 根路径端点"""
        response = requests.get(f"{api_url}/", timeout=10)

        assert response.status_code == 200, f"根路径访问失败: {response.status_code}"
        data = response.json()
        assert data["code"] == 0, f"响应code错误: {data.get('code')}"
        assert "version" in data["data"], "缺少version字段"
        assert data["data"]["name"] == "AI Eval Platform", (
            f"服务名称错误: {data['data'].get('name')}"
        )

    def test_health_check_timeout(self, api_url):
        """场景H-004: 健康检查超时"""
        start_time = time.time()
        try:
            response = requests.get(f"{api_url}/health", timeout=5)
            elapsed = time.time() - start_time
            assert elapsed < 5, f"健康检查响应超时: {elapsed:.2f}s"
            assert response.status_code == 200
        except requests.Timeout:
            pytest.fail("健康检查超时")
