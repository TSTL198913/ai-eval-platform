from unittest.mock import MagicMock

from src.domain.evaluators.qa import QAEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestQAEvaluator:
    """问答质量评估器测试"""

    def setup_method(self):
        self.mock_client = MagicMock()

    def test_evaluate_exact_match(self):
        """测试完全匹配"""
        self.mock_client.chat.return_value = "巴黎"

        evaluator = QAEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_qa_001",
            type="qa",
            payload={"user_input": "法国的首都是哪里？", "expected_output": "巴黎"},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score >= 0.9

    def test_evaluate_no_match(self):
        """测试完全不匹配"""
        self.mock_client.chat.return_value = "伦敦"

        evaluator = QAEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_001",
            type="qa",
            payload={"user_input": "法国的首都是哪里？", "expected_output": "巴黎"},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score < 0.5

    def test_evaluate_missing_user_input(self):
        """测试缺少问题"""
        evaluator = QAEvaluator(self.mock_client)
        request = EvaluationSchema(id="test_001", type="qa", payload={"expected_output": "答案"})

        result = evaluator.evaluate(request)

        assert result.is_valid is False

    def test_evaluate_without_client(self):
        """测试无客户端"""
        evaluator = QAEvaluator(None)
        request = EvaluationSchema(
            id="test_001", type="qa", payload={"user_input": "问题", "expected_output": "答案"}
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True

    def test_evaluate_with_context(self):
        """测试带上下文的问答"""
        self.mock_client.chat.return_value = "正确答案"

        evaluator = QAEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_001",
            type="qa",
            payload={
                "user_input": "基于上下文的问答",
                "expected_output": "正确答案",
                "context": "这是上下文信息",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score >= 0.8
