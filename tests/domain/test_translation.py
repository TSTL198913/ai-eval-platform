"""TranslationEvaluator单元测试"""

import pytest

from src.domain.evaluators.translation import TranslationEvaluator
from src.schemas.evaluation import EvaluationSchema


@pytest.fixture
def evaluator():
    return TranslationEvaluator()

class TestTranslationEvaluatorPositiveCases:
    """正向测试"""
    def test_valid_translation_passes(self, evaluator):
        request = EvaluationSchema(
            id="pos_001",
            type="translation",
            payload={"text": "Hello", "translation": "你好"}
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True

class TestTranslationEvaluatorNegativeCases:
    """负向测试"""
    def test_empty_translation_returns_error(self, evaluator):
        request = EvaluationSchema(
            id="neg_001",
            type="translation",
            payload={"source": "Hello", "translation": ""}
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False

class TestTranslationEvaluatorBoundaryCases:
    """边界测试"""
    def test_none_payload_returns_error(self, evaluator):
        request = EvaluationSchema(id="bound_001", type="translation", payload={})
        result = evaluator.evaluate(request)
        assert result.is_valid is False
