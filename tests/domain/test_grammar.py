"""GrammarEvaluator单元测试"""

import pytest

from src.domain.evaluators.grammar import GrammarEvaluator
from src.schemas.evaluation import EvaluationSchema


@pytest.fixture
def evaluator():
    return GrammarEvaluator()


class TestGrammarEvaluatorPositiveCases:
    """正向测试"""

    def test_correct_grammar_passes(self, evaluator):
        request = EvaluationSchema(
            id="pos_001",
            type="grammar",
            payload={"text": "This is a grammatically correct sentence."},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True


class TestGrammarEvaluatorNegativeCases:
    """负向测试"""

    def test_empty_text_returns_error(self, evaluator):
        request = EvaluationSchema(id="neg_001", type="grammar", payload={"text": ""})
        result = evaluator.evaluate(request)
        assert result.is_valid is False


class TestGrammarEvaluatorBoundaryCases:
    """边界测试"""

    def test_none_payload_returns_error(self, evaluator):
        request = EvaluationSchema(id="bound_001", type="grammar", payload={})
        result = evaluator.evaluate(request)
        assert result.is_valid is False
