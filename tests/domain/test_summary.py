"""SummaryEvaluator单元测试"""

import pytest

from src.domain.evaluators.summary import SummaryEvaluator
from src.schemas.evaluation import EvaluationSchema


@pytest.fixture
def evaluator():
    return SummaryEvaluator()


class TestSummaryEvaluatorPositiveCases:
    """正向测试"""

    def test_valid_summary_passes(self, evaluator):
        request = EvaluationSchema(
            id="pos_001",
            type="summary",
            payload={"text": "Long text here...", "summary": "Short summary."},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True


class TestSummaryEvaluatorNegativeCases:
    """负向测试"""

    def test_empty_summary_returns_error(self, evaluator):
        request = EvaluationSchema(
            id="neg_001", type="summary", payload={"original": "Text", "summary": ""}
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False


class TestSummaryEvaluatorBoundaryCases:
    """边界测试"""

    def test_none_payload_returns_error(self, evaluator):
        request = EvaluationSchema(id="bound_001", type="summary", payload={})
        result = evaluator.evaluate(request)
        assert result.is_valid is False
