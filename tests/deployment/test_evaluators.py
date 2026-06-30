"""
评估器管理部署测试 - 验证评估器功能
场景覆盖: E-001, E-002, E-003, E-004, R-001, R-002, R-003
"""

import pytest
import requests


@pytest.mark.api
class TestEvaluators:
    """评估器管理测试"""

    def test_list_evaluators(self, api_url):
        """场景E-001: 列出所有评估器"""
        response = requests.get(f"{api_url}/api/v1/evaluators", timeout=10)

        assert response.status_code == 200, f"列出评估器失败: {response.status_code}"
        data = response.json()
        assert data["code"] == 0, f"响应code错误: {data.get('code')}"
        assert isinstance(data["data"], list), "data应是列表"
        assert len(data["data"]) > 0, "评估器列表为空"

        names = [e["name"] for e in data["data"]]
        assert "general" in names, "缺少general评估器"
        assert "code" in names, "缺少code评估器"
        assert "semantic" in names, "缺少semantic评估器"
        assert "risk" in names, "缺少risk评估器"

    def test_get_evaluator_detail(self, api_url):
        """场景E-002: 查询单个评估器"""
        response = requests.get(f"{api_url}/api/v1/evaluators/general", timeout=10)

        assert response.status_code == 200, f"查询评估器失败: {response.status_code}"
        data = response.json()
        assert data["code"] == 0, f"响应code错误: {data.get('code')}"
        assert data["data"]["name"] == "general", f"评估器名称错误: {data['data'].get('name')}"
        assert "class_name" in data["data"], "缺少class_name字段"
        assert "description" in data["data"], "缺少description字段"

    def test_get_nonexistent_evaluator(self, api_url):
        """场景E-003: 查询不存在的评估器"""
        response = requests.get(f"{api_url}/api/v1/evaluators/nonexistent_xyz_123", timeout=10)

        assert response.status_code == 404, (
            f"查询不存在评估器应返回404，实际返回: {response.status_code}"
        )
        data = response.json()
        assert data["code"] == 404, f"响应code错误: {data.get('code')}"

    def test_evaluator_sql_injection_protection(self, api_url):
        """场景E-004: SQL注入防护"""
        malicious_input = "general'; DROP TABLE users--"
        response = requests.get(f"{api_url}/api/v1/evaluators/{malicious_input}", timeout=10)

        assert response.status_code == 404, f"SQL注入应被拦截，实际返回: {response.status_code}"

        response = requests.get(
            f"{api_url}/api/v1/evaluators/general%3B%20DROP%20TABLE", timeout=10
        )
        assert response.status_code == 404, (
            f"URL编码的SQL注入应被拦截，实际返回: {response.status_code}"
        )

    def test_evaluate_submit_request(self, api_url, session_token):
        """场景R-001: 提交评测请求"""
        headers = {"Authorization": f"Bearer {session_token}"}
        response = requests.post(
            f"{api_url}/api/v1/evaluate",
            headers=headers,
            json={
                "id": "deploy_test_case_001",
                "type": "general",
                "payload": {
                    "user_input": "What is AI?",
                    "expected_output": "AI stands for Artificial Intelligence",
                },
            },
            timeout=30,
        )

        assert response.status_code == 200, f"提交评测失败: {response.status_code}"
        data = response.json()
        assert data["code"] == 0, f"响应code错误: {data.get('code')}"
        assert "id" in data["data"], "缺少id字段"
        assert "score" in data["data"], "缺少score字段"
        assert "type" in data["data"], "缺少type字段"
        assert data["data"]["type"] == "general", f"评估器类型错误: {data['data'].get('type')}"

    def test_evaluate_missing_required_fields(self, api_url, session_token):
        """场景R-002: 缺少必填字段"""
        headers = {"Authorization": f"Bearer {session_token}"}

        response = requests.post(
            f"{api_url}/api/v1/evaluate",
            headers=headers,
            json={"id": "test_case", "payload": {"user_input": "test"}},
            timeout=10,
        )
        assert response.status_code == 422, f"缺少type应返回422，实际返回: {response.status_code}"

        response = requests.post(
            f"{api_url}/api/v1/evaluate",
            headers=headers,
            json={"type": "general", "payload": {"user_input": "test"}},
            timeout=10,
        )
        assert response.status_code == 422, f"缺少id应返回422，实际返回: {response.status_code}"

        response = requests.post(
            f"{api_url}/api/v1/evaluate",
            headers=headers,
            json={"id": "test_case", "type": "general"},
            timeout=10,
        )
        assert response.status_code == 422, (
            f"缺少payload应返回422，实际返回: {response.status_code}"
        )

    def test_evaluate_unknown_evaluator_type(self, api_url, session_token):
        """场景R-003: 未知评估器类型"""
        headers = {"Authorization": f"Bearer {session_token}"}
        response = requests.post(
            f"{api_url}/api/v1/evaluate",
            headers=headers,
            json={
                "id": "unknown_type_case",
                "type": "definitely_not_registered_evaluator_xyz",
                "payload": {"user_input": "test"},
            },
            timeout=10,
        )

        assert response.status_code in (400, 422), (
            f"未知评估器类型应返回400/422，实际返回: {response.status_code}"
        )
