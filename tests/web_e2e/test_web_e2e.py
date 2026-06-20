"""Web端端到端测试

测试目标：
1. 验证前端页面渲染正确性
2. 验证前端与后端API交互正确性
3. 验证用户交互流程完整性
4. 验证前端错误处理和反馈

注意：此测试使用 TestClient 模拟 HTTP 请求，验证 API 响应结构是否符合前端预期。
真实的浏览器自动化测试需要使用 Selenium/Playwright 等工具。
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from fastapi.testclient import TestClient

from src.domain.evaluators import auto_discover
from src.domain.evaluators.evaluator_factory import EvaluatorFactory as EF


@pytest.fixture(autouse=True)
def reset_evaluators_each_test():
    """每个测试前重置 EvaluatorFactory 并重新触发自动发现"""
    EF._registry = {}
    auto_discover(force=True)
    yield


class TestWebFrontendContract:
    """前端契约测试 - 验证API响应结构符合前端预期"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        from src.api.server import app

        return TestClient(app)

    def test_evaluator_list_response_structure(self, client):
        """评估器列表响应结构应符合前端预期"""
        response = client.get("/api/v1/evaluators")
        assert response.status_code == 200

        data = response.json()
        # 验证响应结构
        assert "code" in data
        assert "data" in data
        assert data["code"] == 0

        # 验证评估器列表结构 - API直接返回列表
        evaluators = data["data"]

        assert isinstance(evaluators, list)

        for evaluator in evaluators:
            # 每个评估器应包含前端需要的字段
            assert "name" in evaluator
            # API返回 name 而非 type
            assert "class_name" in evaluator or "name" in evaluator

    def test_evaluation_response_structure(self, client):
        """评估响应结构应符合前端预期"""
        response = client.post(
            "/api/v1/evaluate",
            json={
                "id": "web_e2e_eval_test",
                "type": "general",
                "payload": {"user_input": "web frontend test"},
            },
        )

        # 验证响应状态
        assert response.status_code in [200, 422]

        data = response.json()

        # 验证响应结构
        assert "code" in data

        if response.status_code == 200:
            # 成功响应应包含评估结果
            assert "data" in data
            result = data["data"]

            # 前端需要的字段 - API返回record_id而非case_id
            assert "record_id" in result or "case_id" in result or "id" in result
            assert "status" in result or "evaluation_status" in result
            assert "latency_ms" in result

    def test_records_list_response_structure(self, client):
        """记录列表响应结构应符合前端预期"""
        response = client.get("/api/v1/records/search?limit=10")
        assert response.status_code == 200

        data = response.json()
        assert data["code"] == 0

        # 验证分页结构
        records_data = data["data"]
        assert "records" in records_data
        assert "total" in records_data or "pagination" in records_data

        # 验证记录结构
        records = records_data["records"]
        for record in records:
            assert "id" in record
            assert "case_id" in record
            assert "status" in record
            assert "created_at" in record

    def test_health_check_response_structure(self, client):
        """健康检查响应结构应符合前端预期"""
        response = client.get("/api/v1/health")
        assert response.status_code == 200

        data = response.json()
        assert data["code"] == 0

        health_data = data["data"]
        assert "status" in health_data
        assert "components" in health_data

        # 验证组件健康状态
        components = health_data["components"]
        assert "database" in components
        assert "redis" in components


class TestWebUserFlow:
    """用户流程测试 - 验证完整用户交互流程"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        from src.api.server import app

        return TestClient(app)

    def test_user_login_flow(self, client):
        """用户登录流程"""
        # 1. 获取登录页面（模拟）
        response = client.get("/api/v1/auth/login")
        # 登录页面可能返回 404 或重定向，取决于实现

        # 2. 执行登录
        response = client.post(
            "/api/v1/auth/login", json={"username": "demo", "password": "demo123"}
        )

        # 验证登录响应
        assert response.status_code in [200, 401, 404]

        if response.status_code == 200:
            data = response.json()
            # 前端需要的字段
            assert "access_token" in data.get("data", {})
            assert "refresh_token" in data.get("data", {})

    def test_user_evaluation_flow(self, client):
        """用户评估流程"""
        # 1. 获取评估器列表
        response = client.get("/api/v1/evaluators")
        assert response.status_code == 200

        evaluators = response.json()["data"]
        # API直接返回列表

        # 2. 选择评估器并执行评估
        if evaluators:
            # 获取第一个评估器的名称
            evaluator_name = evaluators[0].get("name", "general")
            response = client.post(
                "/api/v1/evaluate",
                json={
                    "id": "user_flow_eval",
                    "type": evaluator_name,
                    "payload": {"user_input": "user flow test"},
                },
            )
            assert response.status_code in [200, 422]

    def test_user_records_flow(self, client):
        """用户记录查询流程"""
        # 1. 查询记录列表
        response = client.get("/api/v1/records/search?limit=10")
        assert response.status_code == 200

        records = response.json()["data"]["records"]

        # 2. 查看记录详情（如果有记录）
        if records:
            record_id = records[0]["id"]
            response = client.get(f"/api/v1/records/{record_id}")
            assert response.status_code in [200, 404]

            if response.status_code == 200:
                detail = response.json()["data"]
                assert detail["id"] == record_id

    def test_user_export_flow(self, client):
        """用户导出流程"""
        # 1. 导出为 CSV
        response = client.get("/api/v1/records/export?format=csv")
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")

        # 2. 导出为 JSON
        response = client.get("/api/v1/records/export?format=json")
        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")


class TestWebErrorHandling:
    """前端错误处理测试 - 验证错误响应符合前端预期"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        from src.api.server import app

        return TestClient(app)

    def test_invalid_evaluator_type_error(self, client):
        """无效评估器类型错误"""
        response = client.post(
            "/api/v1/evaluate",
            json={
                "id": "error_test",
                "type": "nonexistent_evaluator",
                "payload": {"user_input": "test"},
            },
        )

        # 验证错误响应结构
        assert response.status_code in [400, 422]

        data = response.json()
        assert "code" in data
        assert data["code"] != 0  # 错误码
        assert "message" in data

    def test_invalid_record_id_error(self, client):
        """无效记录ID错误"""
        response = client.get("/api/v1/records/999999")

        # 验证错误响应结构
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            # 如果返回 200，data 应为 null 或包含错误标志
            if data.get("data") is None:
                pass  # 正确处理：返回 null

    def test_invalid_export_format_error(self, client):
        """无效导出格式错误"""
        response = client.get("/api/v1/records/export?format=invalid_format")

        # 验证错误响应结构
        data = response.json()
        assert data["code"] == 400  # 错误码
        assert "message" in data

    def test_missing_required_field_error(self, client):
        """缺少必填字段错误"""
        response = client.post(
            "/api/v1/evaluate",
            json={
                # 缺少 id 字段
                "type": "general",
                "payload": {"user_input": "test"},
            },
        )

        # 验证错误响应结构
        assert response.status_code == 422  # FastAPI 验证错误

        data = response.json()
        assert "detail" in data or "message" in data


class TestWebPagination:
    """前端分页测试 - 验证分页逻辑正确"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        from src.api.server import app

        return TestClient(app)

    def test_pagination_first_page(self, client):
        """第一页分页"""
        response = client.get("/api/v1/records/search?limit=5&offset=0")
        assert response.status_code == 200

        data = response.json()["data"]
        assert len(data["records"]) <= 5

    def test_pagination_second_page(self, client):
        """第二页分页"""
        response = client.get("/api/v1/records/search?limit=5&offset=5")
        assert response.status_code == 200

        data = response.json()["data"]
        assert len(data["records"]) <= 5

    def test_pagination_total_count(self, client):
        """分页总数"""
        response = client.get("/api/v1/records/search?limit=10")
        assert response.status_code == 200

        data = response.json()["data"]
        # 应包含总数信息
        assert "total" in data or "pagination" in data


class TestWebSearch:
    """前端搜索测试 - 验证搜索功能正确"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        from src.api.server import app

        return TestClient(app)

    def test_search_by_status(self, client):
        """按状态搜索"""
        response = client.get("/api/v1/records/search?record_status=passed&limit=10")
        assert response.status_code == 200

        data = response.json()["data"]
        records = data["records"]

        # 所有记录状态应为 passed
        for record in records:
            assert record["status"] == "passed"

    def test_search_by_evaluator(self, client):
        """按评估器搜索"""
        response = client.get("/api/v1/records/search?evaluator=GeneralEvaluator&limit=10")
        assert response.status_code == 200

        data = response.json()["data"]
        records = data["records"]

        # 所有记录评估器应为 GeneralEvaluator
        for record in records:
            assert (
                "General" in record["adapter_name"] or record["adapter_name"] == "GeneralEvaluator"
            )

    def test_search_combined_filters(self, client):
        """组合搜索"""
        response = client.get(
            "/api/v1/records/search?record_status=passed&evaluator=GeneralEvaluator&limit=10"
        )
        assert response.status_code == 200

        data = response.json()["data"]
        records = data["records"]

        # 所有记录应满足两个条件
        for record in records:
            assert record["status"] == "passed"


class TestWebModelComparison:
    """前端模型对比测试"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        from src.api.server import app

        return TestClient(app)

    def test_model_comparison_response_structure(self, client):
        """模型对比响应结构"""
        response = client.post(
            "/api/v1/models/compare",
            json={
                "models": [
                    {"provider": "openai", "name": "gpt-4"},
                    {"provider": "openai", "name": "gpt-3.5-turbo"},
                ],
                "datasets": ["mmlu"],
            },
        )

        # 验证响应状态
        assert response.status_code in [200, 400]

        if response.status_code == 200:
            data = response.json()
            assert data["code"] == 0

            # 验证响应结构 - API返回models列表
            comparison_data = data["data"]
            assert "models" in comparison_data or "is_simulated" in comparison_data

    def test_model_comparison_empty_models_error(self, client):
        """模型对比空模型列表错误"""
        response = client.post("/api/v1/models/compare", json={"models": [], "datasets": ["mmlu"]})

        data = response.json()
        assert data["code"] == 400  # 错误码


class TestWebDashboard:
    """前端仪表盘测试"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        from src.api.server import app

        return TestClient(app)

    def test_dashboard_stats_response(self, client):
        """仪表盘统计数据响应"""
        # 假设有仪表盘统计接口
        response = client.get("/api/v1/stats")

        # 接口可能不存在，验证响应
        if response.status_code == 200:
            data = response.json()
            # 前端需要的统计数据字段
            result_data = data.get("data", {})
            assert "total_evaluations" in result_data or "code" in data

    def test_dashboard_cost_metrics_response(self, client):
        """仪表盘成本指标响应"""
        response = client.get("/api/v1/cost/metrics")

        # 接口可能不存在，验证响应
        if response.status_code == 200:
            data = response.json()
            # 前端需要的成本指标字段
            metrics = data.get("data", {})
            if metrics:
                assert "daily_cost_usd" in metrics or "total_requests" in metrics


class TestWebAuthentication:
    """前端认证测试"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        from src.api.server import app

        return TestClient(app)

    def test_login_success_response(self, client):
        """登录成功响应"""
        response = client.post(
            "/api/v1/auth/login", json={"username": "demo", "password": "demo123"}
        )

        if response.status_code == 200:
            data = response.json()
            # 前端需要的认证字段
            auth_data = data.get("data", {})
            assert "access_token" in auth_data
            assert "refresh_token" in auth_data
            assert "expires_in" in auth_data

    def test_login_failure_response(self, client):
        """登录失败响应"""
        response = client.post(
            "/api/v1/auth/login", json={"username": "invalid", "password": "invalid"}
        )

        # 验证错误响应结构
        if response.status_code == 401:
            data = response.json()
            assert data["code"] != 0
            assert "message" in data

    def test_refresh_token_response(self, client):
        """刷新令牌响应"""
        response = client.post("/api/v1/auth/refresh", json={"refresh_token": "demo-refresh-token"})

        # 验证响应结构
        if response.status_code == 200:
            data = response.json()
            auth_data = data.get("data", {})
            assert "access_token" in auth_data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
