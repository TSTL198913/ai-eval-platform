"""QAEvaluator单元测试"""

import pytest

from src.domain.evaluators.qa import QAEvaluator
from src.schemas.evaluation import EvaluationSchema


@pytest.fixture
def evaluator():
    return QAEvaluator()


class TestQAEvaluatorPositiveCases:
    """正向测试"""

    def test_valid_qa_passes(self, evaluator):
        request = EvaluationSchema(
            id="pos_001",
            type="qa",
            payload={"text": "What is Python?", "answer": "Python is a programming language."},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True


class TestQAEvaluatorNegativeCases:
    """负向测试"""

    def test_empty_question_returns_error(self, evaluator):
        request = EvaluationSchema(
            id="neg_001", type="qa", payload={"question": "", "answer": "Some answer"}
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False


class TestQAEvaluatorBoundaryCases:
    """边界测试"""

    def test_none_payload_returns_error(self, evaluator):
        request = EvaluationSchema(id="bound_001", type="qa", payload={})
        result = evaluator.evaluate(request)
        assert result.is_valid is False
