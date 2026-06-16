import pytest
from unittest.mock import MagicMock
from src.schemas.evaluation import EvaluationSchema
from src.domain.evaluators.sentiment import SentimentEvaluator


class TestSentimentEvaluator:
    """情感分析评估器测试"""

    def setup_method(self):
        self.mock_client = MagicMock()

    def test_evaluate_positive_sentiment(self):
        """测试正面情感"""
        self.mock_client.chat.return_value = "positive"

        evaluator = SentimentEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_sentiment_001",
            type="sentiment",
            payload={"user_input": "表达你的感受", "expected_sentiment": "positive"}
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score is not None
        assert result.data is not None  # data 字段包含情感信息

    def test_evaluate_negative_sentiment(self):
        """测试负面情感"""
        self.mock_client.chat.return_value = "negative"

        evaluator = SentimentEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_001",
            type="sentiment",
            payload={"user_input": "描述你的心情", "expected_sentiment": "negative"}
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True

    def test_evaluate_neutral_sentiment(self):
        """测试中性情感"""
        self.mock_client.chat.return_value = "neutral"

        evaluator = SentimentEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_001",
            type="sentiment",
            payload={"user_input": "描述天气", "expected_sentiment": "neutral"}
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True

    def test_evaluate_missing_user_input(self):
        """测试缺少输入"""
        evaluator = SentimentEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_001",
            type="sentiment",
            payload={"expected_sentiment": "positive"}
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False

    def test_evaluate_without_client(self):
        """测试无客户端"""
        evaluator = SentimentEvaluator(None)
        request = EvaluationSchema(
            id="test_001",
            type="sentiment",
            payload={"user_input": "测试情感", "expected_sentiment": "neutral"}
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.text == "neutral"

    def test_evaluate_score_calculation(self):
        """测试分数计算"""
        self.mock_client.chat.return_value = "positive"

        evaluator = SentimentEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_001",
            type="sentiment",
            payload={"user_input": "心情如何", "expected_sentiment": "positive"}
        )

        result = evaluator.evaluate(request)

        assert 0 <= result.score <= 1

    def test_evaluate_with_expected_sentiment(self):
        """测试期望情感匹配"""
        self.mock_client.chat.return_value = "positive"

        evaluator = SentimentEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_001",
            type="sentiment",
            payload={"user_input": "表达开心", "expected_sentiment": "positive"}
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0
