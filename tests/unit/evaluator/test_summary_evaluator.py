"""
SummaryEvaluator 专项测试
测试目标：验证SummaryEvaluator的actual_output校验、相似度评分等功能
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.summary import SummaryEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestSummaryEvaluatorPositiveCases:
    """正向测试 - 正常输入"""

    @staticmethod
    def test_valid_actual_output_with_expected():
        """有actual_output和expected_output时计算相似度"""
        target = SummaryEvaluator(client=None)
        request = EvaluationSchema(
            id="sum_001",
            type="summary",
            payload={
                "actual_output": "AI是人工智能",
                "expected_output": "AI是人工智能的缩写",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score is not None
        assert 0.0 <= result.score <= 1.0

    @staticmethod
    def test_identical_summary_gets_full_score():
        """相同摘要得满分"""
        target = SummaryEvaluator(client=None)
        request = EvaluationSchema(
            id="sum_002",
            type="summary",
            payload={
                "actual_output": "完全相同的摘要",
                "expected_output": "完全相同的摘要",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0


class TestSummaryEvaluatorNegativeCases:
    """负向测试 - 错误输入"""

    @staticmethod
    def test_empty_actual_output_returns_error():
        """空actual_output应返回错误"""
        target = SummaryEvaluator(client=None)
        request = EvaluationSchema(
            id="sum_neg_001",
            type="summary",
            payload={"actual_output": "", "expected_output": "预期摘要"},
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert "actual_output" in result.error

    @staticmethod
    def test_missing_actual_output_returns_error():
        """缺少actual_output应返回错误"""
        target = SummaryEvaluator(client=None)
        request = EvaluationSchema(
            id="sum_neg_002",
            type="summary",
            payload={"expected_output": "预期摘要"},
        )
        result = target.evaluate(request)

        assert result.is_valid is False

    @staticmethod
    def test_missing_expected_output_returns_error():
        """缺少expected_output应返回错误"""
        target = SummaryEvaluator(client=None)
        request = EvaluationSchema(
            id="sum_neg_003",
            type="summary",
            payload={"actual_output": "实际摘要"},
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert "expected_output" in result.error


class TestSummaryEvaluatorBoundaryCases:
    """边界测试 - 边界值"""

    @staticmethod
    def test_high_similarity_summary():
        """高相似度摘要"""
        target = SummaryEvaluator(client=None)
        request = EvaluationSchema(
            id="sum_bound_001",
            type="summary",
            payload={
                "actual_output": "人工智能是计算机科学的分支",
                "expected_output": "人工智能是计算机科学的分支",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0

    @staticmethod
    def test_low_similarity_summary():
        """低相似度摘要"""
        target = SummaryEvaluator(client=None)
        request = EvaluationSchema(
            id="sum_bound_002",
            type="summary",
            payload={
                "actual_output": "今天天气很好",
                "expected_output": "AI是人工智能的缩写",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score < 0.5
