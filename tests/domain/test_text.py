"""TextEvaluator单元测试"""

import pytest

from src.domain.evaluators.text import create_text_evaluator
from src.schemas.evaluation import EvaluationSchema


@pytest.fixture
def evaluator():
    return create_text_evaluator()


class TestTextEvaluatorPositiveCases:
    """正向测试"""

    def test_valid_text_passes(self, evaluator):
        """TextEvaluator需要LLM client，无client时返回错误"""
        request = EvaluationSchema(
            id="pos_001", type="text", payload={"text": "This is a valid text input."}
        )
        result = evaluator.evaluate(request)
        # 无LLM client时返回错误
        assert result.is_valid is False
        assert "LLM client" in result.error


class TestTextEvaluatorNegativeCases:
    """负向测试"""

    def test_empty_text_returns_error(self, evaluator):
        request = EvaluationSchema(id="neg_001", type="text", payload={"text": ""})
        result = evaluator.evaluate(request)
        assert result.is_valid is False


class TestTextEvaluatorBoundaryCases:
    """边界测试"""

    def test_none_payload_returns_error(self, evaluator):
        request = EvaluationSchema(id="bound_001", type="text", payload={})
        result = evaluator.evaluate(request)
        assert result.is_valid is False
