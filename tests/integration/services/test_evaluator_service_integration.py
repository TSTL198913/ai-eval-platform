"""
Evaluator Service 集成测试
测试目标：验证 Service 层与 Engine、Repository 的完整集成流程
"""

from unittest.mock import MagicMock, patch

import pytest

from src.services.evaluator_svc import _normalize_raw_data, run_evaluation_service


@pytest.fixture
def mock_llm_client():
    client = MagicMock()
    client.config = MagicMock()
    client.config.model_name = "test-model"
    client.chat.return_value = "模型生成的回答"
    return client


class TestDataNormalization:
    def test_normalize_with_payload(self):
        raw_data = {
            "id": "test-001",
            "type": "semantic",
            "payload": {"prompt": "测试", "actual_output": "输出"},
            "metadata": {"source": "test"},
        }
        result = _normalize_raw_data(raw_data)
        assert result == raw_data

    def test_normalize_without_payload(self):
        raw_data = {
            "id": "test-002",
            "type": "semantic",
            "prompt": "测试问题",
            "actual_output": "实际回答",
            "expected_output": "期望回答",
            "metadata": {"source": "test"},
        }
        result = _normalize_raw_data(raw_data)
        assert "payload" in result
        assert result["payload"]["prompt"] == "测试问题"
        assert result["payload"]["actual_output"] == "实际回答"

    def test_normalize_preserves_model_info(self):
        raw_data = {
            "id": "test-003",
            "type": "semantic",
            "prompt": "测试",
            "model_provider": "openai",
            "model_name": "gpt-4",
        }
        result = _normalize_raw_data(raw_data)
        assert result["model_provider"] == "openai"
        assert result["model_name"] == "gpt-4"

    def test_normalize_without_id(self):
        raw_data = {"type": "semantic", "prompt": "测试"}
        result = _normalize_raw_data(raw_data)
        assert result["id"] == "unknown"


class TestEvaluationServiceWorkflow:
    def test_run_evaluation_service_with_client(self, mock_llm_client):
        raw_data = {
            "id": "service_001",
            "type": "semantic",
            "payload": {"actual_output": "测试输出", "expected_output": "期望输出"},
        }
        result = run_evaluation_service(raw_data, client=mock_llm_client)
        assert result["status"] == "success"
        assert result["record_id"] == "service_001"
        assert result["evaluation_status"] == "passed"

    def test_run_evaluation_service_with_model_provider(self):
        raw_data = {
            "id": "service_002",
            "type": "semantic",
            "model_provider": "deepseek",
            "model_name": "deepseek-chat",
            "payload": {"actual_output": "测试输出", "expected_output": "测试输出"},
        }
        result = run_evaluation_service(raw_data)
        assert result["status"] == "success"
        assert result["evaluation_status"] == "passed"

    def test_run_evaluation_service_online_mode(self, mock_llm_client):
        raw_data = {
            "id": "service_004",
            "type": "semantic",
            "payload": {"prompt": "如何重置密码？", "expected_output": "点击设置重置密码"},
        }
        result = run_evaluation_service(raw_data, client=mock_llm_client)
        assert result["status"] == "success"
        assert result["data"] is not None

    def test_run_evaluation_service_persist_result(self):
        raw_data = {
            "id": "service_005",
            "type": "semantic",
            "payload": {"actual_output": "测试", "expected_output": "测试"},
        }
        result = run_evaluation_service(raw_data)
        assert result["persist"] is True
        assert result["persist_error"] is None


class TestEvaluationServiceExceptionHandling:
    def test_run_evaluation_service_unknown_evaluator(self, mock_llm_client):
        raw_data = {
            "id": "service_err_001",
            "type": "unknown_evaluator_type",
            "payload": {"actual_output": "测试"},
        }
        result = run_evaluation_service(raw_data, client=mock_llm_client)
        assert result["status"] == "error"
        assert result["code"] == "E2005"

    def test_run_evaluation_service_validation_error(self, mock_llm_client):
        raw_data = {"type": "semantic"}
        result = run_evaluation_service(raw_data, client=mock_llm_client)
        assert result["evaluation_status"] == "failed"
        assert result["data"]["is_valid"] is False

    def test_run_evaluation_service_persist_failure(self, mock_llm_client):
        raw_data = {
            "id": "service_err_002",
            "type": "semantic",
            "payload": {"actual_output": "测试", "expected_output": "测试"},
        }
        with patch("src.services.evaluator_svc._repository") as mock_repo:
            mock_repo.save.side_effect = Exception("DB connection failed")
            result = run_evaluation_service(raw_data, client=mock_llm_client)
        assert result["status"] == "success"
        assert result["persist"] is False

    def test_run_evaluation_service_internal_error(self, mock_llm_client):
        with patch("src.services.evaluator_svc.EvaluationEngine") as mock_engine:
            mock_engine.return_value.run.side_effect = RuntimeError("Unexpected error")
            raw_data = {
                "id": "service_err_003",
                "type": "semantic",
                "payload": {"actual_output": "测试"},
            }
            result = run_evaluation_service(raw_data, client=mock_llm_client)
        assert result["status"] == "error"
        assert result["code"] == "INTERNAL_ERROR"


class TestEvaluationServiceBusinessScenarios:
    def test_customer_service_evaluation(self, mock_llm_client):
        raw_data = {
            "id": "business_cs_001",
            "type": "semantic",
            "payload": {
                "prompt": "如何申请退款？",
                "actual_output": "您可以在订单页面申请退款",
                "expected_output": "在订单详情页点击退款按钮，填写退款原因后提交。",
            },
        }
        result = run_evaluation_service(raw_data, client=mock_llm_client)
        assert result["status"] == "success"
        assert result["record_id"] == "business_cs_001"
        assert result["data"]["score"] is not None
        assert 0.0 <= result["data"]["score"] <= 1.0

    def test_batch_evaluation_scenario(self, mock_llm_client):
        batch_data = [
            {
                "id": "batch_001",
                "type": "semantic",
                "payload": {"actual_output": "回答1", "expected_output": "期望1"},
            },
            {"id": "batch_002", "type": "grammar", "payload": {"actual_output": "正确的句子。"}},
            {
                "id": "batch_003",
                "type": "text",
                "payload": {"actual_output": "完全匹配", "expected_output": "完全匹配"},
            },
        ]
        for data in batch_data:
            result = run_evaluation_service(data, client=mock_llm_client)
            assert result["status"] == "success"
            assert result["record_id"] == data["id"]

    def test_full_lifecycle_scenario(self, mock_llm_client):
        raw_data = {
            "id": "lifecycle_001",
            "type": "semantic",
            "payload": {
                "prompt": "解释什么是机器学习",
                "expected_output": "机器学习是人工智能的分支，通过算法让计算机从数据中学习。",
            },
        }
        result = run_evaluation_service(raw_data, client=mock_llm_client)
        assert result["status"] == "success"
        assert result["evaluation_status"] == "passed"
        assert result["data"]["is_valid"] is True
        assert result["data"]["score"] is not None
        assert result["persist"] is True
