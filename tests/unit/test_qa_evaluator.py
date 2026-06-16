import pytest
from unittest.mock import MagicMock
from src.schemas.evaluation import EvaluationSchema
from src.domain.evaluators.qa import QAEvaluator


class TestQAEvaluator:
    """问答质量评估器测试"""

    def setup_method(self):
        self.mock_client = MagicMock()

    def test_evaluate_correct_answer(self):
        """测试正确答案"""
        self.mock_client.chat.return_value = "巴黎是法国的首都。"

        evaluator = QAEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_qa_001",
            type="qa",
            payload={
                "user_input": "法国的首都是哪里？",
                "expected_output": "巴黎"
            }
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score is not None
        assert 0 <= result.score <= 1

    def test_evaluate_incorrect_answer(self):
        """测试错误答案"""
        self.mock_client.chat.return_value = "伦敦是法国的首都。"

        evaluator = QAEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_001",
            type="qa",
            payload={"user_input": "法国的首都是哪里？", "expected_output": "巴黎"}
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score is not None

    def test_evaluate_missing_user_input(self):
        """测试缺少问题"""
        evaluator = QAEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_001",
            type="qa",
            payload={"expected_output": "答案"}
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False

    def test_evaluate_without_client(self):
        """测试无客户端"""
        evaluator = QAEvaluator(None)
        request = EvaluationSchema(
            id="test_001",
            type="qa",
            payload={"user_input": "问题", "expected_output": "答案"}
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True

    def test_evaluate_partial_answer(self):
        """测试部分正确答案"""
        self.mock_client.chat.return_value = "巴黎是法国的首都。"

        evaluator = QAEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_001",
            type="qa",
            payload={"user_input": "法国的首都", "expected_output": "巴黎"}
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True

    def test_evaluate_with_context(self):
        """测试带上下文的问答"""
        self.mock_client.chat.return_value = "根据文章，这是正确的答案。"

        evaluator = QAEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_001",
            type="qa",
            payload={
                "user_input": "基于上下文的问答",
                "expected_output": "正确答案"
            }
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True

    def test_evaluate_score_range(self):
        """测试分数范围"""
        self.mock_client.chat.return_value = "答案"

        evaluator = QAEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_001",
            type="qa",
            payload={"user_input": "问题", "expected_output": "答案"}
        )

        result = evaluator.evaluate(request)

        assert 0 <= result.score <= 1
