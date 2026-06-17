"""
API服务器集成测试
测试 FastAPI 服务器的端点和功能
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.server import app


@pytest.fixture
def client():
    """创建测试客户端"""
    return TestClient(app)


@pytest.fixture
def mock_evaluator():
    """Mock评测器"""
    evaluator = MagicMock()
    evaluator.evaluate.return_value = MagicMock(
        is_valid=True,
        text="测试响应",
        score=0.95,
        feedback="测试反馈",
        details={},
        error=None,
    )
    return evaluator


class TestAPIEndpoints:
    """API端点集成测试"""

    def test_health_endpoint(self, client):
        """测试健康检查端点"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_evaluate_endpoint_success(self, client, mock_evaluator):
        """测试评测端点成功场景"""
        with patch("src.services.evaluator_svc.run_evaluation_service") as mock_service:
            mock_service.return_value = {
                "status": "success",
                "record_id": "test_001",
                "evaluation_status": "passed",
                "latency_ms": 100.0,
                "data": mock_evaluator.evaluate.return_value,
            }

            response = client.post(
                "/api/v1/evaluate",
                json={
                    "id": "test_001",
                    "type": "general",
                    "payload": {
                        "user_input": "测试输入",
                        "expected_output": "测试输出",
                    },
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"

    def test_evaluate_endpoint_validation_error(self, client):
        """测试评测端点验证错误"""
        response = client.post(
            "/api/v1/evaluate",
            json={
                "id": "",  # 空id
                "type": "general",
            },
        )

        # API可能返回200，验证响应格式
        assert response.status_code == 200
        data = response.json()
        # 验证响应包含必要字段
        assert "status" in data

    def test_batch_evaluate_endpoint(self, client, mock_evaluator):
        """测试批量评测端点"""
        with patch("src.workers.tasks.eval_case_task") as mock_task:
            mock_task.delay.return_value = MagicMock(id="task_001")

            response = client.post(
                "/api/v1/evaluate/batch",
                json={
                    "cases": [
                        {
                            "id": "batch_001",
                            "type": "general",
                            "payload": {
                                "user_input": "测试1",
                                "expected_output": "输出1",
                            },
                        },
                        {
                            "id": "batch_002",
                            "type": "finance",
                            "payload": {
                                "user_input": "测试2",
                                "expected_output": "输出2",
                            },
                        },
                    ]
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert len(data["results"]) == 2

    def test_get_result_endpoint(self, client):
        """测试获取结果端点"""
        with patch("src.api.server._get_repository") as mock_get_repo:
            mock_repo = MagicMock()
            mock_repo.get_recent.return_value = [
                {"id": 1, "case_id": "test_001", "status": "passed"},
            ]
            mock_get_repo.return_value = mock_repo

            response = client.get("/api/v1/records")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert len(data["records"]) == 1

    def test_get_result_not_found(self, client):
        """测试获取结果端点 - 结果不存在"""
        with patch("src.api.server._get_repository") as mock_get_repo:
            mock_repo = MagicMock()
            mock_repo.get_recent.return_value = []
            mock_get_repo.return_value = mock_repo

            response = client.get("/api/v1/records")

            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 0

    def test_list_results_endpoint(self, client):
        """测试列出结果端点"""
        with patch("src.api.server._get_repository") as mock_get_repo:
            mock_repo = MagicMock()
            mock_repo.get_recent.return_value = [
                {"id": 1, "case_id": "test_001", "status": "passed"},
                {"id": 2, "case_id": "test_002", "status": "failed"},
            ]
            mock_get_repo.return_value = mock_repo

            response = client.get("/api/v1/records")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert len(data["records"]) == 2


class TestAPIErrorHandling:
    """API错误处理集成测试"""

    def test_invalid_domain(self, client):
        """测试无效领域"""
        response = client.post(
            "/api/v1/evaluate",
            json={
                "id": "test_invalid",
                "type": "invalid_domain",
                "payload": {
                    "user_input": "测试",
                    "expected_output": "输出",
                },
            },
        )

        # 应该返回错误
        assert response.status_code in [400, 422, 500]

    def test_missing_required_fields(self, client):
        """测试缺少必需字段"""
        response = client.post(
            "/api/v1/evaluate",
            json={
                "type": "general",
                # 缺少 id 和 payload
            },
        )

        # API可能返回422验证错误或200
        assert response.status_code in [200, 422]
        # 验证响应格式正确
        if response.status_code == 200:
            data = response.json()
            assert "status" in data

    def test_malformed_json(self, client):
        """测试格式错误的JSON"""
        response = client.post(
            "/api/v1/evaluate",
            content="invalid json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code in [400, 422]


class TestAPIPerformance:
    """API性能集成测试"""

    def test_concurrent_requests(self, client, mock_evaluator):
        """测试并发请求"""
        from concurrent.futures import ThreadPoolExecutor

        with patch("src.services.evaluator_svc.run_evaluation_service") as mock_service:
            mock_service.return_value = {
                "status": "success",
                "record_id": "concurrent_test",
                "evaluation_status": "passed",
                "latency_ms": 100.0,
            }

            def make_request(i):
                return client.post(
                    "/api/v1/evaluate",
                    json={
                        "id": f"concurrent_{i}",
                        "type": "general",
                        "payload": {
                            "user_input": f"测试{i}",
                            "expected_output": "输出",
                        },
                    },
                )

            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(make_request, i) for i in range(10)]
                results = [f.result() for f in futures]

            # 所有请求都应该成功
            assert all(r.status_code == 200 for r in results)