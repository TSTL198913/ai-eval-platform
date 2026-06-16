import pytest
from unittest.mock import MagicMock
from src.schemas.evaluation import EvaluationSchema
from src.domain.evaluators.translation import TranslationEvaluator


class TestTranslationEvaluator:
    """翻译质量评估器测试"""

    def setup_method(self):
        self.mock_client = MagicMock()

    def test_evaluate_good_translation(self):
        """测试良好翻译"""
        self.mock_client.chat.return_value = "Hello, how are you?"

        evaluator = TranslationEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_trans_001",
            type="translation",
            payload={
                "user_input": "你好，你好吗？",
                "expected_output": "Hello, how are you?"
            }
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score is not None

    def test_evaluate_missing_user_input(self):
        """测试缺少输入"""
        evaluator = TranslationEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_001",
            type="translation",
            payload={"expected_output": "translation"}
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False

    def test_evaluate_without_client(self):
        """测试无客户端"""
        evaluator = TranslationEvaluator(None)
        request = EvaluationSchema(
            id="test_001",
            type="translation",
            payload={"user_input": "你好", "expected_output": "Hello"}
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True

    def test_evaluate_score_range(self):
        """测试分数范围"""
        self.mock_client.chat.return_value = "Good morning"

        evaluator = TranslationEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_001",
            type="translation",
            payload={"user_input": "早上好", "expected_output": "Good morning"}
        )

        result = evaluator.evaluate(request)

        assert 0 <= result.score <= 1

    def test_evaluate_poor_translation(self):
        """测试较差翻译"""
        self.mock_client.chat.return_value = "xyz abc"

        evaluator = TranslationEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_001",
            type="translation",
            payload={"user_input": "你好", "expected_output": "Hello"}
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
