"""SemanticEvaluator单元测试"""
import pytest
from unittest.mock import MagicMock
from src.domain.evaluators.semantic import SemanticEvaluator
from src.schemas.evaluation import EvaluationSchema

@pytest.fixture
def evaluator():
    return SemanticEvaluator()

class TestSemanticEvaluatorPositiveCases:
    """正向测试"""
    def test_semantic_match_passes(self, evaluator):
        request = EvaluationSchema(
            id="pos_001",
            type="semantic",
            payload={"text": "Hello world", "expected_output": "Hello world"}
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True

class TestSemanticEvaluatorNegativeCases:
    """负向测试"""
    def test_empty_text_returns_error(self, evaluator):
        request = EvaluationSchema(
            id="neg_001",
            type="semantic",
            payload={"text1": "", "text2": "Hello"}
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False

class TestSemanticEvaluatorBoundaryCases:
    """边界测试"""
    def test_none_payload_returns_error(self, evaluator):
        request = EvaluationSchema(id="bound_001", type="semantic", payload={})
        result = evaluator.evaluate(request)
        assert result.is_valid is False
