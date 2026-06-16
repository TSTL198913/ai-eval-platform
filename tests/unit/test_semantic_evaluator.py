from unittest.mock import MagicMock

from src.domain.evaluators.semantic import SemanticEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestSemanticEvaluator:
    """语义相似度评估器测试"""

    def setup_method(self):
        self.mock_client = MagicMock()

    def test_evaluate_with_valid_input(self):
        """测试有效输入"""
        self.mock_client.chat.return_value = "这是一个测试回答"

        evaluator = SemanticEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_semantic_001",
            type="semantic",
            payload={"user_input": "你好", "expected_output": "你好"},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score is not None
        assert 0 <= result.score <= 1

    def test_evaluate_missing_user_input(self):
        """测试缺少用户输入"""
        evaluator = SemanticEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_001", type="semantic", payload={"expected_output": "expected"}
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "不能为空" in result.error

    def test_evaluate_missing_expected_output(self):
        """测试缺少期望输出"""
        evaluator = SemanticEvaluator(self.mock_client)
        request = EvaluationSchema(id="test_001", type="semantic", payload={"user_input": "hello"})

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "不能为空" in result.error

    def test_evaluate_without_client(self):
        """测试无客户端时使用原始输入"""
        evaluator = SemanticEvaluator(None)
        request = EvaluationSchema(
            id="test_001",
            type="semantic",
            payload={"user_input": "你好", "expected_output": "你好"},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.text == "你好"

    def test_evaluate_exact_match(self):
        """测试完全匹配"""
        self.mock_client.chat.return_value = "今天天气很好"

        evaluator = SemanticEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_001",
            type="semantic",
            payload={"user_input": "天气如何", "expected_output": "今天天气很好"},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score >= 0.8

    def test_evaluate_no_match(self):
        """测试完全不匹配"""
        self.mock_client.chat.return_value = "完全不相关的内容"

        evaluator = SemanticEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_001",
            type="semantic",
            payload={"user_input": "你好", "expected_output": "天气很好"},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score < 0.5
