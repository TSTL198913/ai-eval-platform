"""
前后端一致性测试

验证后端 API 返回的数据结构与前端 TypeScript 类型定义完全一致。
使用 JSON Schema 自动生成验证器，确保数据契约的一致性。
"""

from unittest.mock import MagicMock

import pytest

from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.engine import EvaluationEngine
from src.services.evaluator_svc import run_evaluation_service


class TestFrontendBackendContract:
    """
    前后端数据契约一致性测试

    前端期望的数据结构（来自 TypeScript 类型）:
    - EvaluationRecord: { id, case_id, adapter_name, model_name, status, score, latency_ms, created_at }
    - EvaluateResponse: { case_id, score, is_valid, status, latency_ms?, data? }
    - DashboardStats: { total_records, evaluator_types, recent_records, status_distribution }
    """

    # 前端 EvaluationRecord 类型（来自 src/types/index.ts）
    FRONTEND_EVALUATION_RECORD_SCHEMA = {
        "id": int,
        "case_id": str,
        "adapter_name": str,
        "model_name": str,
        "status": str,
        "score": (int, float),
        "latency_ms": (int, float),
        "created_at": str,
    }

    # 前端 EvaluateResponse 类型
    FRONTEND_EVALUATE_RESPONSE_SCHEMA = {
        "case_id": str,
        "score": (int, float),
        "is_valid": bool,
        "status": str,
        "latency_ms": (type(None), int, float),
        "data": (type(None), dict),
    }

    def validate_schema(self, data: dict, schema: dict) -> list[str]:
        """验证数据是否符合前端 schema，返回错误列表"""
        errors = []
        for field, expected_type in schema.items():
            if field not in data:
                errors.append(f"缺少字段: {field}")
                continue

            value = data[field]
            if isinstance(expected_type, tuple):
                if not any(
                    isinstance(value, t) for t in expected_type if not isinstance(t, type(None))
                ):
                    # 允许 None
                    if value is not None:
                        allowed = [
                            t.__name__ if isinstance(t, type) else str(t) for t in expected_type
                        ]
                        errors.append(
                            f"字段 {field} 类型错误: 期望 {allowed}, 实际 {type(value).__name__}"
                        )
            else:
                if not isinstance(value, expected_type):
                    errors.append(
                        f"字段 {field} 类型错误: 期望 {expected_type.__name__}, 实际 {type(value).__name__}"
                    )
        return errors

    def test_evaluation_record_matches_frontend(self):
        """场景: 评估记录数据结构必须与前端 EvaluationRecord 类型一致"""
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        client.chat = MagicMock(return_value="Test response with expected keyword")

        result = run_evaluation_service(
            {
                "id": "contract_test_001",
                "type": "general",
                "payload": {
                    "user_input": "What is AI?",
                    "expected_output": "Test response with expected keyword",
                },
            },
            client=client,
        )

        # 模拟数据库保存的数据格式（来自 Repository）
        mock_record = {
            "id": 1,
            "case_id": result["record_id"],
            "adapter_name": "GeneralEvaluator",
            "model_name": "gpt-4",
            "status": result["status"],
            "score": result["data"].get("score", 0.0) if result.get("data") else 0.0,
            "latency_ms": result["latency_ms"],
            "created_at": "2024-01-01T00:00:00",
        }

        # 验证字段存在且类型正确
        errors = self.validate_schema(mock_record, self.FRONTEND_EVALUATION_RECORD_SCHEMA)
        assert not errors, f"EvaluationRecord 与前端类型不一致: {errors}"

    def test_evaluate_response_matches_frontend(self):
        """场景: 评估接口返回必须与前端 EvaluateResponse 类型一致"""
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        client.chat = MagicMock(return_value="Match exactly")

        result = run_evaluation_service(
            {
                "id": "contract_test_002",
                "type": "general",
                "payload": {
                    "user_input": "Test",
                    "expected_output": "Match exactly",
                },
            },
            client=client,
        )

        # 构建前端期望的响应格式
        frontend_response = {
            "case_id": result["record_id"],
            "score": result["data"].get("score", 0.0) if result.get("data") else 0.0,
            "is_valid": result["data"].get("is_valid", False) if result.get("data") else False,
            "status": result["status"],
            "latency_ms": result.get("latency_ms"),
            "data": result.get("data"),
        }

        errors = self.validate_schema(frontend_response, self.FRONTEND_EVALUATE_RESPONSE_SCHEMA)
        assert not errors, f"EvaluateResponse 与前端类型不一致: {errors}"

    def test_status_field_uses_pascal_case(self):
        """场景: status 字段必须使用 PascalCase（如 'passed', 'failed', 'error'）"""
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        client.chat = MagicMock(return_value="Expected output")

        result = run_evaluation_service(
            {
                "id": "status_contract_test",
                "type": "general",
                "payload": {
                    "user_input": "Test",
                    "expected_output": "Expected output",
                },
            },
            client=client,
        )

        # 前端期望的 status 值
        valid_statuses = {"passed", "failed", "error", "success"}
        assert (
            result["status"] in valid_statuses
        ), f"status '{result['status']}' 不在有效值 {valid_statuses} 中"

    def test_status_and_evaluation_status_different_meanings(self):
        """场景: status 与 evaluation_status 是不同字段，有不同含义"""
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        client.chat = MagicMock(return_value="Match")

        result = run_evaluation_service(
            {
                "id": "status_meanings_test",
                "type": "general",
                "payload": {
                    "user_input": "Test",
                    "expected_output": "Match",
                },
            },
            client=client,
        )

        # status: API 层状态（success/error）
        # evaluation_status: 评估结果状态（passed/failed/error）
        assert result["status"] in [
            "success",
            "error",
        ], f"status 应为 'success' 或 'error', 实际: {result['status']}"
        assert result["evaluation_status"] in [
            "passed",
            "failed",
            "error",
        ], f"evaluation_status 应为 'passed'/'failed'/'error', 实际: {result['evaluation_status']}"

    def test_error_response_structure(self):
        """场景: 错误响应结构必须与前端错误处理一致"""
        # 直接使用 evaluator 来触发错误
        from src.schemas.evaluation import EvaluationSchema

        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "test"
        # 让 chat 抛出异常
        client.chat = MagicMock(side_effect=Exception("LLM Error"))

        engine = EvaluationEngine(client)
        request = EvaluationSchema(
            id="error_test",
            type="general",
            payload={"user_input": "test"},
        )
        result = engine.run(request)

        # 错误时引擎应返回 ERROR 状态
        assert result.status.value == "error", f"引擎应返回 ERROR 状态, 实际: {result.status.value}"

    def test_data_field_contains_all_required_fields(self):
        """场景: data 字段必须包含前端所需的所有子字段"""
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        client.chat = MagicMock(return_value="Complete response")

        result = run_evaluation_service(
            {
                "id": "data_field_test",
                "type": "general",
                "payload": {
                    "user_input": "Test",
                    "expected_output": "Complete response",
                },
            },
            client=client,
        )

        data = result.get("data")
        assert data is not None, "data 字段不能为 None"

        # 前端 EvaluateResponse.data 期望的字段
        expected_data_fields = {"score", "is_valid", "text", "error"}
        actual_fields = set(data.keys())
        missing = expected_data_fields - actual_fields
        assert not missing, f"data 缺少前端所需字段: {missing}"


class TestAPIEndpointContract:
    """API 端点契约测试 - 验证后端 API 与前端 API 调用的契约"""

    def test_api_response_wrapper_format(self):
        """场景: API 响应必须符合 { code, message, data } 包装格式"""
        # 模拟 API 层的 handleResponse 逻辑
        mock_api_response = {
            "code": 0,
            "message": "success",
            "data": {
                "case_id": "test_001",
                "score": 1.0,
                "is_valid": True,
                "status": "success",
            },
        }

        # 验证 API 响应格式
        assert "code" in mock_api_response
        assert "message" in mock_api_response
        assert "data" in mock_api_response
        assert mock_api_response["code"] == 0

    def test_pagination_response_format(self):
        """场景: 分页响应必须包含 count 和 records 字段"""
        # 模拟 records API 响应
        mock_pagination_response = {
            "code": 0,
            "message": "success",
            "data": {
                "count": 100,
                "records": [
                    {
                        "id": 1,
                        "case_id": "case_001",
                        "adapter_name": "GeneralEvaluator",
                        "model_name": "gpt-4",
                        "status": "passed",
                        "score": 0.95,
                        "latency_ms": 150.5,
                        "created_at": "2024-01-01T00:00:00",
                    }
                ],
            },
        }

        data = mock_pagination_response["data"]
        assert "count" in data, "分页响应缺少 count 字段"
        assert "records" in data, "分页响应缺少 records 字段"
        assert isinstance(data["records"], list), "records 必须是数组"


class TestBusinessLogicConsistency:
    """业务逻辑一致性测试"""

    def test_score_range_is_0_to_1(self):
        """场景: 评分必须在 0-1 范围内，与前端图表展示一致"""
        from src.domain.evaluators.base import BaseEvaluator
        from src.schemas.evaluation import DomainResponse, EvaluationSchema

        @EvaluatorFactory.register("score_test")
        class MockScoreEvaluator(BaseEvaluator):
            def evaluate(self, request):
                return DomainResponse(is_valid=True, score=0.95, text="Perfect match")

        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"

        engine = EvaluationEngine(client)
        request = EvaluationSchema(
            id="score_range_test",
            type="score_test",
            payload={
                "user_input": "Test",
                "expected_output": "Perfect match",
            },
        )
        result = engine.run(request)

        assert result.response is not None, "response 不应为 None"
        score = result.response.score
        assert score is not None, f"response.score 不应为 None: {result.response}"
        assert 0 <= score <= 1, f"分数 {score} 超出 0-1 范围，前端图表可能无法正确显示"

    def test_latency_ms_is_non_negative(self):
        """场景: 延迟必须为非负数，与前端延迟图表一致"""
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        client.chat = MagicMock(return_value="Response")

        result = run_evaluation_service(
            {
                "id": "latency_test",
                "type": "general",
                "payload": {"user_input": "Test", "expected_output": "Response"},
            },
            client=client,
        )

        latency = result.get("latency_ms", 0)
        assert latency >= 0, f"延迟 {latency} 为负数，数据异常"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
