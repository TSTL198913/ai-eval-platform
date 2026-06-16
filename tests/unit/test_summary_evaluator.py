from unittest.mock import MagicMock

from src.domain.evaluators.summary import SummaryEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestSummaryEvaluator:
    """摘要质量评估器测试"""

    def setup_method(self):
        self.mock_client = MagicMock()

    def test_evaluate_good_summary(self):
        """测试良好摘要"""
        self.mock_client.chat.return_value = "AI technology is rapidly evolving."

        evaluator = SummaryEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_summary_001",
            type="summary",
            payload={
                "user_input": "长文章关于AI...",
                "expected_output": "AI technology is rapidly evolving.",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score >= 0.8

    def test_evaluate_poor_summary(self):
        """测试较差摘要"""
        self.mock_client.chat.return_value = "无关内容"

        evaluator = SummaryEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_001",
            type="summary",
            payload={"user_input": "长文章关于AI...", "expected_output": "AI technology"},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score < 0.5

    def test_evaluate_missing_user_input(self):
        """测试缺少输入"""
        evaluator = SummaryEvaluator(self.mock_client)
        request = EvaluationSchema(id="test_001", type="summary", payload={})

        result = evaluator.evaluate(request)

        assert result.is_valid is False

    def test_evaluate_without_client(self):
        """测试无客户端"""
        evaluator = SummaryEvaluator(None)
        request = EvaluationSchema(
            id="test_001",
            type="summary",
            payload={"user_input": "长文本", "expected_output": "摘要"},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
