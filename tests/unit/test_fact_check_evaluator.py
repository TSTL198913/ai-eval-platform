from unittest.mock import MagicMock

from src.domain.evaluators.fact_check import FactCheckEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestFactCheckEvaluator:
    """事实核查评估器测试"""

    def setup_method(self):
        self.mock_client = MagicMock()

    def test_evaluate_true_statement(self):
        """测试真实陈述"""
        self.mock_client.chat.return_value = "结果: true\n理由: 地球确实是圆的"

        evaluator = FactCheckEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_fact_001", type="fact_check", payload={"user_input": "地球是圆的"}
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0

    def test_evaluate_false_statement(self):
        """测试虚假陈述"""
        self.mock_client.chat.return_value = "结果: false\n理由: 地球不是平的"

        evaluator = FactCheckEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_001", type="fact_check", payload={"user_input": "地球是平的"}
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 0.0

    def test_evaluate_missing_user_input(self):
        """测试缺少输入"""
        evaluator = FactCheckEvaluator(self.mock_client)
        request = EvaluationSchema(id="test_001", type="fact_check", payload={})

        result = evaluator.evaluate(request)

        assert result.is_valid is False

    def test_evaluate_without_client(self):
        """测试无客户端"""
        evaluator = FactCheckEvaluator(None)
        request = EvaluationSchema(
            id="test_001", type="fact_check", payload={"user_input": "事实陈述"}
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0
