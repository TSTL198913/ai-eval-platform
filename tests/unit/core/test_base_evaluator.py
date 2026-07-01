"""BaseEvaluator公共方法单元测试"""

import pytest

from src.domain.evaluators.base import BaseEvaluator
from src.schemas.evaluation import DomainResponse, EvaluationSchema, EvaluatorStatus, ConfidenceLevel


class ConcreteEvaluator(BaseEvaluator):
    """BaseEvaluator的具体实现用于测试"""

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        return DomainResponse(evaluation_status=EvaluatorStatus.SUCCESS, text="测试评估完成", score=1.0, confidence=0.9, confidence_level=ConfidenceLevel.HIGH, data={})


class TestBaseEvaluatorHelpers:
    """BaseEvaluator辅助方法测试"""

    @pytest.fixture
    def evaluator(self):
        return ConcreteEvaluator()

    def test_get_payload_data_existing_key(self, evaluator):
        """获取存在的payload数据"""
        request = EvaluationSchema(id="test", type="test", payload={"key": "value"})
        result = evaluator.get_payload_data(request, "key")
        assert result == "value"

    def test_get_payload_data_missing_key(self, evaluator):
        """获取不存在的payload数据应返回默认值"""
        request = EvaluationSchema(id="test", type="test", payload={"key": "value"})
        result = evaluator.get_payload_data(request, "missing", default="default")
        assert result == "default"

    def test_get_input_text_from_user_input(self, evaluator):
        """从user_input获取输入文本"""
        request = EvaluationSchema(id="test", type="test", payload={"user_input": "test input"})
        result = evaluator.get_input_text(request)
        assert result == "test input"

    def test_get_input_text_from_text(self, evaluator):
        """从text字段获取输入文本"""
        request = EvaluationSchema(id="test", type="test", payload={"text": "test input"})
        result = evaluator.get_input_text(request)
        assert result == "test input"

    def test_get_input_text_prefers_user_input(self, evaluator):
        """优先从user_input获取"""
        request = EvaluationSchema(
            id="test", type="test", payload={"user_input": "user_input", "text": "text"}
        )
        result = evaluator.get_input_text(request)
        assert result == "user_input"

    def test_get_input_text_default(self, evaluator):
        """无输入时返回默认值"""
        request = EvaluationSchema(id="test", type="test", payload={})
        result = evaluator.get_input_text(request, default="default text")
        assert result == "default text"


class TestCreateErrorResponse:
    """错误响应创建方法测试"""

    @pytest.fixture
    def evaluator(self):
        return ConcreteEvaluator()

    def test_create_error_response_basic(self, evaluator):
        """创建基本错误响应"""
        response = evaluator.create_error_response("错误消息")

        assert response.is_valid is False
        assert response.error == "错误消息"
        assert response.metadata == {}

    def test_create_error_response_with_code(self, evaluator):
        """创建带错误码的错误响应"""
        response = evaluator.create_error_response("错误消息", error_code="ERR_001")

        assert response.is_valid is False
        assert response.error == "错误消息"
        assert response.metadata == {"error_code": "ERR_001"}

    def test_create_error_response_with_metadata(self, evaluator):
        """创建带metadata的错误响应"""
        response = evaluator.create_error_response("错误消息", metadata={"field": "value"})

        assert response.is_valid is False
        assert response.metadata == {"field": "value"}

    def test_create_error_response_with_code_and_metadata(self, evaluator):
        """创建带错误码和metadata的错误响应"""
        response = evaluator.create_error_response(
            "错误消息", error_code="ERR_001", metadata={"field": "value"}
        )

        assert response.is_valid is False
        assert response.metadata == {"error_code": "ERR_001", "field": "value"}

    def test_create_error_response_metadata_override(self, evaluator):
        """error_code应覆盖已有的metadata"""
        response = evaluator.create_error_response(
            "错误消息", error_code="ERR_001", metadata={"error_code": "old_code"}
        )

        # 新的error_code应覆盖旧的
        assert response.metadata["error_code"] == "ERR_001"


class TestCreateSuccessResponse:
    """成功响应创建方法测试"""

    @pytest.fixture
    def evaluator(self):
        return ConcreteEvaluator()

    def test_create_success_response_basic(self, evaluator):
        """创建基本成功响应"""
        response = evaluator.create_success_response()

        assert response.is_valid is True
        assert response.text == "评估完成"
        assert response.score == 1.0
        assert response.data == {}

    def test_create_success_response_custom_text(self, evaluator):
        """创建自定义文本的成功响应"""
        response = evaluator.create_success_response(text="自定义文本")

        assert response.is_valid is True
        assert response.text == "自定义文本"

    def test_create_success_response_custom_score(self, evaluator):
        """创建自定义分数的成功响应"""
        response = evaluator.create_success_response(score=0.85)

        assert response.is_valid is True
        assert response.score == 0.85

    def test_create_success_response_custom_data(self, evaluator):
        """创建带数据的成功响应"""
        response = evaluator.create_success_response(data={"key": "value"})

        assert response.is_valid is True
        assert response.data == {"key": "value"}

    def test_create_success_response_full_custom(self, evaluator):
        """创建完全自定义的成功响应"""
        response = evaluator.create_success_response(
            text="评估完成", score=0.9, data={"result": "ok"}
        )

        assert response.is_valid is True
        assert response.text == "评估完成"
        assert response.score == 0.9
        assert response.data == {"result": "ok"}

    def test_create_success_response_none_data_becomes_empty(self, evaluator):
        """None数据应转换为空字典"""
        response = evaluator.create_success_response(data=None)

        assert response.is_valid is True
        assert response.data == {}


class TestSafeEvaluate:
    """安全评估方法测试"""

    @pytest.fixture
    def evaluator(self):
        return ConcreteEvaluator()

    def test_safe_evaluate_normal_request(self, evaluator):
        """正常请求应正常返回"""
        request = EvaluationSchema(id="test", type="test", payload={})
        response = evaluator.safe_evaluate(request)

        assert response.is_valid is True

    def test_safe_evaluate_returns_none(self, evaluator):
        """评估器返回None应捕获并返回错误"""

        class NoneEvaluator(BaseEvaluator):
            def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
                return None  # type: ignore

        evaluator = NoneEvaluator()
        request = EvaluationSchema(id="test", type="test", payload={})
        response = evaluator.safe_evaluate(request)

        assert response.is_valid is False
        assert "None" in response.error


class TestRequireClient:
    """客户端需求方法测试"""

    def test_require_client_not_configured(self):
        """未配置客户端应返回错误"""
        evaluator = ConcreteEvaluator(client=None)
        response = evaluator.require_client_with_error()

        assert response is not None
        assert response.is_valid is False
        assert "LLM 客户端" in response.error

    def test_require_client_configured(self):
        """已配置客户端应返回None"""
        from unittest.mock import MagicMock

        from src.domain.models.base import BaseLLMClient

        mock_client = MagicMock(spec=BaseLLMClient)
        evaluator = ConcreteEvaluator(client=mock_client)
        response = evaluator.require_client_with_error()

        assert response is None
