from unittest.mock import MagicMock

from src.domain.evaluators.general import GeneralEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestGeneralEvaluator:
    """通用评估器测试"""

    def setup_method(self):
        self.mock_client = MagicMock()

    def test_evaluate_with_client(self):
        """测试有客户端评估"""
        self.mock_client.chat.return_value = "LLM响应"

        evaluator = GeneralEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_general",
            type="general",
            payload={"user_input": "测试问题"},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0

    def test_evaluate_with_expected_output(self):
        """测试包含期望输出"""
        self.mock_client.chat.return_value = "期望的回答"

        evaluator = GeneralEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_expected",
            type="general",
            payload={
                "user_input": "测试问题",
                "expected_output": "期望的回答",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0

    def test_evaluate_without_client(self):
        """测试无客户端模式"""
        evaluator = GeneralEvaluator(None)
        request = EvaluationSchema(
            id="test_no_client",
            type="general",
            payload={"user_input": "测试问题"},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0

    def test_evaluate_missing_user_input(self):
        """测试缺少输入"""
        evaluator = GeneralEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_missing",
            type="general",
            payload={},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "不能为空" in result.error