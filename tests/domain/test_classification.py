"""ClassificationEvaluator单元测试"""
import pytest
from unittest.mock import MagicMock
from src.domain.evaluators.classification import ClassificationEvaluator
from src.schemas.evaluation import EvaluationSchema

@pytest.fixture
def evaluator():
    return ClassificationEvaluator()

class TestClassificationEvaluatorPositiveCases:
    """正向测试"""
    def test_valid_classification_passes(self, evaluator):
        request = EvaluationSchema(
            id="pos_001",
            type="classification",
            payload={"text": "This is a positive review", "expected_label": "positive"}
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.score >= 0.0

class TestClassificationEvaluatorNegativeCases:
    """负向测试"""
    def test_empty_text_returns_error(self, evaluator):
        request = EvaluationSchema(
            id="neg_001",
            type="classification",
            payload={"text": ""}
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False

class TestClassificationEvaluatorBoundaryCases:
    """边界测试"""
    def test_none_payload_returns_error(self, evaluator):
        request = EvaluationSchema(id="bound_001", type="classification", payload={})
        result = evaluator.evaluate(request)
        assert result.is_valid is False
