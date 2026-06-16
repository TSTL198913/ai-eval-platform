import pytest
from unittest.mock import MagicMock
from src.schemas.evaluation import EvaluationSchema
from src.domain.evaluators.fact_check import FactCheckEvaluator


class TestFactCheckEvaluator:
    """事实核查评估器测试"""

    def setup_method(self):
        self.mock_client = MagicMock()

    def test_evaluate_true_statement(self):
        """测试真实陈述"""
        self.mock_client.chat.return_value = "true"

        evaluator = FactCheckEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_fact_001",
            type="fact_check",
            payload={
                "user_input": "地球是圆的",
                "expected_output": "true"
            }
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score is not None

    def test_evaluate_false_statement(self):
        """测试虚假陈述"""
        self.mock_client.chat.return_value = "false"

        evaluator = FactCheckEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_001",
            type="fact_check",
            payload={"user_input": "地球是平的", "expected_output": "false"}
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score is not None

    def test_evaluate_missing_user_input(self):
        """测试缺少输入"""
        evaluator = FactCheckEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_001",
            type="fact_check",
            payload={}
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False

    def test_evaluate_without_client(self):
        """测试无客户端"""
        evaluator = FactCheckEvaluator(None)
        request = EvaluationSchema(
            id="test_001",
            type="fact_check",
            payload={"user_input": "事实陈述", "expected_output": "true"}
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True

    def test_evaluate_score_calculation(self):
        """测试分数计算"""
        self.mock_client.chat.return_value = "true"

        evaluator = FactCheckEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_001",
            type="fact_check",
            payload={"user_input": "测试事实", "expected_output": "true"}
        )

        result = evaluator.evaluate(request)

        assert 0 <= result.score <= 1

    def test_evaluate_partial_match(self):
        """测试部分匹配"""
        self.mock_client.chat.return_value = "mostly true"

        evaluator = FactCheckEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_001",
            type="fact_check",
            payload={"user_input": "大部分正确的陈述", "expected_output": "true"}
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
