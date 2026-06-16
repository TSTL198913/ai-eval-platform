from unittest.mock import MagicMock

from src.domain.evaluators.sentiment import SentimentEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestSentimentEvaluator:
    """情感分析评估器测试"""

    def setup_method(self):
        self.mock_client = MagicMock()

    def test_evaluate_sentiment_match(self):
        """测试情感匹配"""
        for sentiment in ["positive", "negative", "neutral"]:
            self.mock_client.chat.return_value = sentiment

            evaluator = SentimentEvaluator(self.mock_client)
            request = EvaluationSchema(
                id=f"test_{sentiment}",
                type="sentiment",
                payload={"user_input": "测试文本", "expected_sentiment": sentiment},
            )

            result = evaluator.evaluate(request)

            assert result.is_valid is True
            assert result.score == 1.0

    def test_evaluate_sentiment_mismatch(self):
        """测试情感不匹配"""
        self.mock_client.chat.return_value = "positive"

        evaluator = SentimentEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_mismatch",
            type="sentiment",
            payload={"user_input": "测试文本", "expected_sentiment": "negative"},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 0.0

    def test_evaluate_missing_user_input(self):
        """测试缺少输入"""
        evaluator = SentimentEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_001", type="sentiment", payload={"expected_sentiment": "positive"}
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False

    def test_evaluate_without_client(self):
        """测试无客户端"""
        evaluator = SentimentEvaluator(None)
        request = EvaluationSchema(
            id="test_001",
            type="sentiment",
            payload={"user_input": "测试情感", "expected_sentiment": "neutral"},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.text == "neutral"
