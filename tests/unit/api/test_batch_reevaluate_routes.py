"""
批量重新评估路由测试
测试目标：验证批量重新评估API的正确性
关键发现：批量重新评估需要处理多种异常场景
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.server import app


@pytest.fixture
def client():
    """创建测试客户端"""
    return TestClient(app)


class TestBatchReevaluatePositiveCases:
    """正向测试 - 正常批量重新评估"""

    @patch("src.api.routes.records_routes._get_data_service")
    @patch("src.api.routes.records_routes.run_evaluation_service")
    def test_batch_reevaluate_returns_success(self, mock_eval, mock_svc, client):
        """批量重新评估应返回成功"""
        # Mock数据服务
        mock_data_svc = MagicMock()
        mock_data_svc.get_by_id.return_value = {
            "id": 1,
            "adapter_name": "general",
            "response_data": {"payload": {"user_input": "test"}},
        }
        mock_svc.return_value = mock_data_svc

        # Mock评估服务
        mock_eval.return_value = {
            "status": "passed",
            "data": {"score": 0.9},
            "latency_ms": 100,
        }

        response = client.post(
            "/api/v1/records/batch/reevaluate",
            json={"record_ids": [1, 2, 3]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["total"] == 3
        assert data["data"]["success_count"] == 3
        assert data["data"]["failed_count"] == 0
        assert len(data["data"]["results"]) == 3

    @patch("src.api.routes.records_routes._get_data_service")
    @patch("src.api.routes.records_routes.run_evaluation_service")
    def test_batch_reevaluate_single_record(self, mock_eval, mock_svc, client):
        """单个记录重新评估应正常"""
        mock_data_svc = MagicMock()
        mock_data_svc.get_by_id.return_value = {
            "id": 1,
            "adapter_name": "security",
            "response_data": {"payload": {"user_input": "test input"}},
        }
        mock_svc.return_value = mock_data_svc
        mock_eval.return_value = {
            "status": "passed",
            "data": {"score": 1.0},
            "latency_ms": 50,
        }

        response = client.post(
            "/api/v1/records/batch/reevaluate",
            json={"record_ids": [1]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total"] == 1
        assert data["data"]["success_count"] == 1


class TestBatchReevaluateNegativeCases:
    """负向测试 - 错误输入"""

    def test_batch_reevaluate_empty_ids_returns_error(self, client):
        """空ID列表应返回错误"""
        response = client.post(
            "/api/v1/records/batch/reevaluate",
            json={"record_ids": []},
        )
        assert response.status_code == 422

    def test_batch_reevaluate_without_ids_returns_error(self, client):
        """缺少ID列表应返回错误"""
        response = client.post(
            "/api/v1/records/batch/reevaluate",
            json={},
        )
        assert response.status_code == 422

    @patch("src.api.routes.records_routes._get_data_service")
    def test_batch_reevaluate_nonexistent_record(self, mock_svc, client):
        """不存在的记录应标记为失败"""
        mock_data_svc = MagicMock()
        mock_data_svc.get_by_id.return_value = None
        mock_svc.return_value = mock_data_svc

        response = client.post(
            "/api/v1/records/batch/reevaluate",
            json={"record_ids": [999]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["success_count"] == 0
        assert data["data"]["failed_count"] == 1
        assert data["data"]["results"][0]["status"] == "error"
        assert "不存在" in data["data"]["results"][0]["message"]

    @patch("src.api.routes.records_routes._get_data_service")
    @patch("src.api.routes.records_routes.run_evaluation_service")
    def test_batch_reevaluate_partial_failure(self, mock_eval, mock_svc, client):
        """部分失败应正确统计"""
        mock_data_svc = MagicMock()

        def get_by_id_side_effect(record_id):
            if record_id == 1:
                return {
                    "id": 1,
                    "adapter_name": "general",
                    "response_data": {"payload": {"user_input": "test"}},
                }
            return None

        mock_data_svc.get_by_id.side_effect = get_by_id_side_effect
        mock_svc.return_value = mock_data_svc
        mock_eval.return_value = {
            "status": "passed",
            "data": {"score": 0.9},
            "latency_ms": 100,
        }

        response = client.post(
            "/api/v1/records/batch/reevaluate",
            json={"record_ids": [1, 999]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total"] == 2
        assert data["data"]["success_count"] == 1
        assert data["data"]["failed_count"] == 1


class TestBatchReevaluateBoundaryCases:
    """边界测试 - 边界值"""

    @patch("src.api.routes.records_routes._get_data_service")
    @patch("src.api.routes.records_routes.run_evaluation_service")
    def test_batch_reevaluate_large_batch(self, mock_eval, mock_svc, client):
        """大批量重新评估应正常处理"""
        mock_data_svc = MagicMock()
        mock_data_svc.get_by_id.return_value = {
            "id": 1,
            "adapter_name": "general",
            "response_data": {"payload": {}},
        }
        mock_svc.return_value = mock_data_svc
        mock_eval.return_value = {"status": "passed", "data": {"score": 0.9}}

        large_ids = list(range(1, 51))
        response = client.post(
            "/api/v1/records/batch/reevaluate",
            json={"record_ids": large_ids},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total"] == 50

    @patch("src.api.routes.records_routes._get_data_service")
    @patch("src.api.routes.records_routes.run_evaluation_service")
    def test_batch_reevaluate_with_missing_payload(self, mock_eval, mock_svc, client):
        """缺少payload的记录应使用空字典"""
        mock_data_svc = MagicMock()
        mock_data_svc.get_by_id.return_value = {
            "id": 1,
            "adapter_name": "general",
            "response_data": {},  # 无payload
        }
        mock_svc.return_value = mock_data_svc
        mock_eval.return_value = {"status": "passed", "data": {"score": 0.9}}

        response = client.post(
            "/api/v1/records/batch/reevaluate",
            json={"record_ids": [1]},
        )
        assert response.status_code == 200


class TestBatchReevaluateExceptionHandling:
    """异常测试 - 异常情况处理"""

    @patch("src.api.routes.records_routes._get_data_service")
    @patch("src.api.routes.records_routes.run_evaluation_service")
    def test_batch_reevaluate_eval_service_exception(self, mock_eval, mock_svc, client):
        """评估服务异常应标记为失败"""
        mock_data_svc = MagicMock()
        mock_data_svc.get_by_id.return_value = {
            "id": 1,
            "adapter_name": "general",
            "response_data": {"payload": {}},
        }
        mock_svc.return_value = mock_data_svc
        mock_eval.side_effect = Exception("LLM service error")

        response = client.post(
            "/api/v1/records/batch/reevaluate",
            json={"record_ids": [1]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["success_count"] == 0
        assert data["data"]["failed_count"] == 1
        assert data["data"]["results"][0]["status"] == "error"


## 自检清单
# - [x] **覆盖完整性**：正向、负向、边界、异常场景已覆盖
# - [x] **断言强度**：验证具体业务逻辑（success_count、failed_count、results）
# - [x] **Mock配置**：所有Mock都设置了return_value或side_effect
# - [x] **测试隔离**：每个测试独立运行，使用patch隔离
# - [x] **命名规范**：遵循test_<功能>_<场景>_<预期>格式
