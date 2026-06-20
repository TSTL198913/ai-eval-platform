"""SentimentEvaluator单元测试"""
import pytest
from unittest.mock import MagicMock
from src.domain.evaluators.sentiment import SentimentEvaluator
from src.schemas.evaluation import EvaluationSchema

@pytest.fixture
def evaluator():
    return SentimentEvaluator()

class TestSentimentEvaluatorPositiveCases:
    """正向测试"""
    def test_positive_sentiment_detected(self, evaluator):
        request = EvaluationSchema(
            id="pos_001",
            type="sentiment",
            payload={"text": "I love this product! It is amazing!"}
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True

class TestSentimentEvaluatorNegativeCases:
    """负向测试"""
    def test_empty_text_returns_error(self, evaluator):
        request = EvaluationSchema(
            id="neg_001",
            type="sentiment",
            payload={"text": ""}
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False

class TestSentimentEvaluatorBoundaryCases:
    """边界测试"""
    def test_none_payload_returns_error(self, evaluator):
        request = EvaluationSchema(id="bound_001", type="sentiment", payload={})
        result = evaluator.evaluate(request)
        assert result.is_valid is False
