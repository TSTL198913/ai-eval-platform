"""
评估配置路由测试
测试目标：验证评估配置API的CRUD操作
关键发现：新增API需要完整的CRUD测试覆盖
"""

import pytest
from fastapi.testclient import TestClient

from src.api.routes.eval_config_routes import _eval_configs
from src.api.server import app


@pytest.fixture(autouse=True)
def reset_config_store():
    """每个测试前清理配置存储"""
    _eval_configs.clear()
    yield
    _eval_configs.clear()


@pytest.fixture
def client():
    """创建测试客户端"""
    return TestClient(app)


class TestEvalConfigRoutesPositiveCases:
    """正向测试 - 正常CRUD操作"""

    def test_create_config_returns_success(self, client):
        """创建配置应返回成功"""
        response = client.post(
            "/api/v1/eval-configs",
            json={
                "name": "测试配置",
                "evaluator_type": "security",
                "config": {"threshold": 0.8},
                "enabled": True,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["name"] == "测试配置"
        assert data["data"]["evaluator_type"] == "security"
        assert data["data"]["enabled"] is True
        assert "id" in data["data"]

    def test_get_all_configs_returns_list(self, client):
        """获取所有配置应返回列表"""
        # 先创建一个配置
        client.post(
            "/api/v1/eval-configs",
            json={
                "name": "配置1",
                "evaluator_type": "general",
                "config": {},
                "enabled": True,
            },
        )
        response = client.get("/api/v1/eval-configs")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert isinstance(data["data"], list)
        assert len(data["data"]) >= 1

    def test_get_single_config_returns_detail(self, client):
        """获取单个配置应返回详情"""
        # 创建配置
        create_response = client.post(
            "/api/v1/eval-configs",
            json={
                "name": "详细配置",
                "evaluator_type": "factuality",
                "config": {"key": "value"},
                "enabled": True,
            },
        )
        assert create_response.status_code == 200
        config_id = create_response.json()["data"]["id"]

        # 获取详情
        response = client.get(f"/api/v1/eval-configs/{config_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["id"] == config_id
        assert data["data"]["name"] == "详细配置"

    def test_update_config_returns_success(self, client):
        """更新配置应返回成功"""
        # 创建配置
        create_response = client.post(
            "/api/v1/eval-configs",
            json={
                "name": "原配置",
                "evaluator_type": "general",
                "config": {},
                "enabled": True,
            },
        )
        assert create_response.status_code == 200
        config_id = create_response.json()["data"]["id"]

        # 更新配置
        response = client.put(
            f"/api/v1/eval-configs/{config_id}",
            json={"name": "更新后的配置", "enabled": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["name"] == "更新后的配置"
        assert data["data"]["enabled"] is False

    def test_delete_config_returns_success(self, client):
        """删除配置应返回成功"""
        # 创建配置
        create_response = client.post(
            "/api/v1/eval-configs",
            json={
                "name": "待删除配置",
                "evaluator_type": "general",
                "config": {},
                "enabled": True,
            },
        )
        assert create_response.status_code == 200
        config_id = create_response.json()["data"]["id"]

        # 删除配置
        response = client.delete(f"/api/v1/eval-configs/{config_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "message" in data["data"]

        # 验证已删除
        get_response = client.get(f"/api/v1/eval-configs/{config_id}")
        assert get_response.status_code == 404


class TestEvalConfigRoutesNegativeCases:
    """负向测试 - 错误输入"""

    def test_create_config_without_name_returns_error(self, client):
        """缺少名称应返回错误"""
        response = client.post(
            "/api/v1/eval-configs",
            json={
                "evaluator_type": "general",
                "config": {},
                "enabled": True,
            },
        )
        assert response.status_code == 422

    def test_create_config_without_evaluator_type_returns_error(self, client):
        """缺少评估器类型应返回错误"""
        response = client.post(
            "/api/v1/eval-configs",
            json={
                "name": "测试配置",
                "config": {},
                "enabled": True,
            },
        )
        assert response.status_code == 422

    def test_get_nonexistent_config_returns_404(self, client):
        """获取不存在的配置应返回404"""
        response = client.get("/api/v1/eval-configs/nonexistent-id")
        assert response.status_code == 404
        data = response.json()
        assert data["code"] == 404

    def test_update_nonexistent_config_returns_404(self, client):
        """更新不存在的配置应返回404"""
        response = client.put(
            "/api/v1/eval-configs/nonexistent-id",
            json={"name": "更新"},
        )
        assert response.status_code == 404

    def test_delete_nonexistent_config_returns_404(self, client):
        """删除不存在的配置应返回404"""
        response = client.delete("/api/v1/eval-configs/nonexistent-id")
        assert response.status_code == 404


class TestEvalConfigRoutesBoundaryCases:
    """边界测试 - 边界值"""

    def test_create_config_with_empty_config_dict(self, client):
        """空配置字典应正常创建"""
        response = client.post(
            "/api/v1/eval-configs",
            json={
                "name": "空配置",
                "evaluator_type": "general",
                "config": {},
                "enabled": True,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["config"] == {}

    def test_create_config_with_long_name(self, client):
        """超长名称应返回错误"""
        response = client.post(
            "/api/v1/eval-configs",
            json={
                "name": "a" * 101,  # 超过100字符限制
                "evaluator_type": "general",
                "config": {},
                "enabled": True,
            },
        )
        assert response.status_code == 422

    def test_create_config_with_complex_config(self, client):
        """复杂嵌套配置应正常创建"""
        complex_config = {
            "threshold": 0.8,
            "nested": {"key": "value", "list": [1, 2, 3]},
            "enabled_features": ["feature1", "feature2"],
        }
        response = client.post(
            "/api/v1/eval-configs",
            json={
                "name": "复杂配置",
                "evaluator_type": "security",
                "config": complex_config,
                "enabled": True,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["config"] == complex_config
