"""
评估配置路由测试 - evaluation_config_routes.py
测试目标：验证评估配置的CRUD操作

注意：标记为external，因为它们依赖：
1. 完整的API服务启动
2. 配置文件管理服务
"""

import pytest

from fastapi.testclient import TestClient

from src.api.server import app

client = TestClient(app)


class TestEvalConfigRoutesPositiveCases:
    """正向测试 - 正常输入"""

    def test_get_all_configs_returns_list(self):
        """获取所有配置应返回列表"""
        response = client.get("/api/v1/eval-configs")
        assert response.status_code == 200
        data = response.json()["data"]
        assert isinstance(data, list)

    @pytest.mark.external
    def test_get_single_config_returns_detail(self):
        """获取单个配置应返回详情"""
        response = client.get("/api/v1/eval-configs/test-config")
        assert response.status_code == 200
        data = response.json()["data"]
        assert "name" in data

    @pytest.mark.external
    def test_create_config_returns_success(self):
        """创建配置应返回成功"""
        response = client.post(
            "/api/v1/eval-configs",
            json={
                "name": "test-config",
                "config": {"model": "gpt-4", "temperature": 0.7},
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["name"] == "test-config"

    @pytest.mark.external
    def test_update_config_returns_success(self):
        """更新配置应返回成功"""
        response = client.put(
            "/api/v1/eval-configs/test-config",
            json={"config": {"model": "gpt-3.5", "temperature": 0.5}},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["name"] == "test-config"

    @pytest.mark.external
    def test_delete_config_returns_success(self):
        """删除配置应返回成功"""
        response = client.delete("/api/v1/eval-configs/test-config")
        # 注意：可能返回200或404（如果不存在）
        assert response.status_code in (200, 404)


class TestEvalConfigRoutesNegativeCases:
    """负向测试 - 错误输入"""

    def test_get_nonexistent_config_returns_404(self):
        """获取不存在的配置应返回404"""
        response = client.get("/api/v1/eval-configs/nonexistent")
        assert response.status_code == 404

    def test_create_config_with_missing_name_returns_422(self):
        """缺少name应返回422"""
        response = client.post(
            "/api/v1/eval-configs",
            json={"config": {"model": "gpt-4"}},
        )
        assert response.status_code == 422

    def test_create_config_with_missing_config_returns_422(self):
        """缺少config应返回422"""
        response = client.post(
            "/api/v1/eval-configs",
            json={"name": "test"},
        )
        assert response.status_code == 422


class TestEvalConfigRoutesBoundaryCases:
    """边界测试 - 边界值"""

    @pytest.mark.external
    def test_create_config_with_empty_config_dict(self):
        """空config字典应正常处理"""
        response = client.post(
            "/api/v1/eval-configs",
            json={"name": "empty-config", "config": {}},
        )
        # 可能返回200或400
        assert response.status_code in (200, 400)

    @pytest.mark.external
    def test_create_config_with_complex_config(self):
        """复杂config应正常处理"""
        response = client.post(
            "/api/v1/eval-configs",
            json={
                "name": "complex-config",
                "config": {
                    "model": "gpt-4",
                    "temperature": 0.7,
                    "max_tokens": 1000,
                    "nested": {"a": 1, "b": 2},
                },
            },
        )
        assert response.status_code == 200
