"""评估器工厂测试"""
from unittest.mock import MagicMock

import pytest

from src.domain.evaluators.evaluator_factory import EvaluatorFactory, EvaluatorProtocol


class TestEvaluatorProtocol:
    """评估器协议测试"""

    def test_protocol_methods(self):
        """测试协议方法"""
        class TestEvaluator:
            def evaluate(self, request):
                return {"result": "ok"}

            def safe_evaluate(self, request):
                try:
                    return self.evaluate(request)
                except Exception:
                    return {"result": "error"}

        evaluator = TestEvaluator()
        assert hasattr(evaluator, "evaluate")
        assert hasattr(evaluator, "safe_evaluate")

        result = evaluator.evaluate("test")
        assert result["result"] == "ok"

        result = evaluator.safe_evaluate("test")
        assert result["result"] == "ok"


class TestEvaluatorFactory:
    """评估器工厂测试"""

    def test_register_and_get(self):
        """测试注册和获取评估器"""
        @EvaluatorFactory.register("test_type")
        class TestEvaluator:
            def __init__(self, client=None):
                self.client = client

            def evaluate(self, request):
                return {"result": "test"}

            def safe_evaluate(self, request):
                return self.evaluate(request)

        evaluator = EvaluatorFactory.get("test_type")
        assert isinstance(evaluator, TestEvaluator)
        assert evaluator.evaluate("test")["result"] == "test"

    def test_register_with_client(self):
        """测试带客户端注册"""
        @EvaluatorFactory.register("test_type_with_client")
        class TestEvaluatorWithClient:
            def __init__(self, client=None):
                self.client = client

            def evaluate(self, request):
                return {"client": self.client is not None}

            def safe_evaluate(self, request):
                return self.evaluate(request)

        mock_client = MagicMock()
        evaluator = EvaluatorFactory.get("test_type_with_client", client=mock_client)
        assert evaluator.client is mock_client
        assert evaluator.evaluate("test")["client"] is True

    def test_get_unknown_type(self):
        """测试获取未知类型"""
        with pytest.raises(ValueError) as exc_info:
            EvaluatorFactory.get("nonexistent_type")

        assert "未找到" in str(exc_info.value)

    def test_list_evaluators(self):
        """测试列出评估器"""
        evaluators = EvaluatorFactory.list_evaluators()
        assert isinstance(evaluators, list)
        assert "general" in evaluators

    def test_get_evaluator_info(self):
        """测试获取评估器信息"""
        info = EvaluatorFactory.get_evaluator_info()
        assert isinstance(info, list)

        general_info = next((e for e in info if e["name"] == "general"), None)
        assert general_info is not None
        assert "name" in general_info
        assert "class_name" in general_info
        assert "docstring" in general_info

    def test_register_decorator_returns_class(self):
        """测试注册装饰器返回类"""
        @EvaluatorFactory.register("decorator_test")
        class DecoratorTestEvaluator:
            def evaluate(self, request):
                return {}

            def safe_evaluate(self, request):
                return {}

        assert DecoratorTestEvaluator is not None