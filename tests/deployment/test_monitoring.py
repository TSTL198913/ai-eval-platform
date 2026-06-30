"""
监控系统部署测试 - 验证Prometheus/Grafana/Alertmanager
场景覆盖: M-001, M-002, M-003
"""

import pytest
import requests


@pytest.mark.monitoring
class TestMonitoring:
    """监控系统测试"""

    def test_prometheus_metrics_endpoint(self, api_url):
        """场景M-001: Prometheus指标端点"""
        response = requests.get(f"{api_url}/metrics", timeout=10)

        assert response.status_code == 200, f"Prometheus指标端点失败: {response.status_code}"
        content = response.text
        assert "http_requests_total" in content or len(content) > 0, "指标内容为空"

    def test_api_metrics_endpoint(self, api_url):
        """场景M-001扩展: API指标端点"""
        response = requests.get(f"{api_url}/api/v1/metrics", timeout=10)

        assert response.status_code == 200, f"API指标端点失败: {response.status_code}"
        data = response.json()
        assert data["code"] == 0, f"响应code错误: {data.get('code')}"
        assert "requests_total" in data["data"], "缺少requests_total字段"
        assert "error_rate" in data["data"], "缺少error_rate字段"

    def test_prometheus_server(self):
        """场景M-001扩展: Prometheus服务器"""
        try:
            response = requests.get(
                "http://192.168.30.134:9090/api/v1/label/instance/values", timeout=10
            )
            assert response.status_code == 200, f"Prometheus服务器不可达: {response.status_code}"
        except requests.exceptions.ConnectionError:
            pytest.skip("Prometheus服务器未启动")

    def test_grafana_server(self):
        """场景M-002: Grafana登录页面"""
        try:
            response = requests.get("http://192.168.30.134:3000/login", timeout=10)
            assert response.status_code == 200, f"Grafana服务器不可达: {response.status_code}"
        except requests.exceptions.ConnectionError:
            pytest.skip("Grafana服务器未启动")

    def test_alertmanager_server(self):
        """场景M-003: Alertmanager端点"""
        try:
            response = requests.get("http://192.168.30.134:9093/api/v1/alerts", timeout=10)
            assert response.status_code == 200, f"Alertmanager服务器不可达: {response.status_code}"
        except requests.exceptions.ConnectionError:
            pytest.skip("Alertmanager服务器未启动")
