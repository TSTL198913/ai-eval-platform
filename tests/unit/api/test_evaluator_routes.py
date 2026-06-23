"""
评估器路由单元测试
测试目标：验证评估器列表查询、详情查询、配置管理等端点
"""

from fastapi.testclient import TestClient

from src.api.server import app

client = TestClient(app)


class TestEvaluatorRoutesPositiveCases:
    """正向测试 - 正常输入"""

    def test_get_all_evaluators_returns_200(self):
        """获取所有评估器列表应返回200"""
        response = client.get("/api/v1/evaluators")
        assert response.status_code == 200
        assert response.json()["code"] == 0
        assert isinstance(response.json()["data"], list)
        assert len(response.json()["data"]) > 0

    def test_get_all_evaluators_contains_required_fields(self):
        """评估器列表应包含必要字段"""
        response = client.get("/api/v1/evaluators")
        data = response.json()["data"]
        if data:
            evaluator = data[0]
            assert "name" in evaluator
            assert "class_name" in evaluator
            assert "docstring" in evaluator
            assert "module" in evaluator

    def test_get_evaluator_detail_returns_200(self):
        """获取评估器详情应返回200"""
        response = client.get("/api/v1/evaluators/general")
        assert response.status_code == 200
        assert response.json()["code"] == 0
        assert response.json()["data"]["name"] == "general"

    def test_get_evaluator_detail_contains_class_name(self):
        """评估器详情应包含类名"""
        response = client.get("/api/v1/evaluators/general")
        assert "class_name" in response.json()["data"]


class TestEvaluatorRoutesNegativeCases:
    """负向测试 - 错误输入"""

    def test_get_evaluator_detail_invalid_name_returns_404(self):
        """无效评估器名称应返回404"""
        response = client.get("/api/v1/evaluators/invalid@name")
        assert response.status_code == 404

    def test_get_evaluator_detail_nonexistent_returns_404(self):
        """不存在的评估器应返回404"""
        response = client.get("/api/v1/evaluators/nonexistent_evaluator_xyz")
        assert response.status_code == 404

    def test_get_evaluator_detail_empty_name_redirects(self):
        """空名称应重定向到列表"""
        response = client.get("/api/v1/evaluators/")
        assert response.status_code == 200
        assert isinstance(response.json()["data"], list)


class TestEvaluatorRoutesBoundaryCases:
    """边界测试 - 边界值"""

    def test_get_evaluator_detail_with_special_characters(self):
        """包含特殊字符的名称应返回404"""
        response = client.get("/api/v1/evaluators/test;DROP")
        assert response.status_code == 404

    def test_get_evaluator_detail_with_sql_injection(self):
        """SQL注入尝试应返回404"""
        response = client.get("/api/v1/evaluators/' OR '1'='1")
        assert response.status_code == 404

    def test_get_all_evaluators_empty_registry(self):
        """空注册表应返回空列表"""
        from src.domain.evaluators import EVALUATOR_REGISTRY

        original = EVALUATOR_REGISTRY.copy()
        EVALUATOR_REGISTRY.clear()
        try:
            response = client.get("/api/v1/evaluators")
            assert response.status_code == 200
            assert response.json()["data"] == []
        finally:
            EVALUATOR_REGISTRY.update(original)


class TestEvaluatorRoutesValidation:
    """验证逻辑测试"""

    def test_validate_evaluator_name_valid(self):
        """验证评估器名称验证函数"""
        from src.api.common import validate_evaluator_name

        assert validate_evaluator_name("general") is True
        assert validate_evaluator_name("llm_as_judge") is True
        assert validate_evaluator_name("test_evaluator_123") is True

    def test_validate_evaluator_name_invalid(self):
        """无效评估器名称应返回False"""
        from src.api.common import validate_evaluator_name

        assert validate_evaluator_name("invalid@name") is False
        assert validate_evaluator_name("test;DROP") is False
        assert validate_evaluator_name("") is False
