"""
TextMatchEvaluator - 文本匹配评估器专项测试
测试目标：验证TextMatchEvaluator的actual_output校验、相似度评分等核心功能
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.text import TextMatchEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestTextMatchEvaluatorPositiveCases:
    """正向测试 - 正常输入"""

    @staticmethod
    def test_valid_actual_output_with_expected_output():
        """合法actual_output+expected_output应返回is_valid=True"""
        target = TextMatchEvaluator(client=None)
        request = EvaluationSchema(
            id="text_001",
            type="text",
            payload={
                "actual_output": "AI是人工智能的缩写",
                "expected_output": "AI是人工智能的缩写",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0

    @staticmethod
    def test_partial_similarity_returns_score():
        """部分相似应返回相应分数"""
        target = TextMatchEvaluator(client=None)
        request = EvaluationSchema(
            id="text_002",
            type="text",
            payload={
                "actual_output": "机器学习是AI的分支",
                "expected_output": "机器学习是AI的一个分支",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert 0.0 <= result.score <= 1.0


class TestTextMatchEvaluatorNegativeCases:
    """负向测试 - 错误输入"""

    @staticmethod
    def test_empty_actual_output_returns_error():
        """空actual_output应返回is_valid=False"""
        target = TextMatchEvaluator(client=None)
        request = EvaluationSchema(
            id="text_neg_001",
            type="text",
            payload={"actual_output": "", "expected_output": "预期输出"},
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert "actual_output" in result.error

    @staticmethod
    def test_missing_actual_output_returns_error():
        """缺少actual_output应返回错误"""
        target = TextMatchEvaluator(client=None)
        request = EvaluationSchema(
            id="text_neg_002",
            type="text",
            payload={"expected_output": "预期输出"},
        )
        result = target.evaluate(request)

        assert result.is_valid is False

    @staticmethod
    def test_missing_expected_output_returns_error():
        """缺少expected_output应返回错误"""
        target = TextMatchEvaluator(client=None)
        request = EvaluationSchema(
            id="text_neg_003",
            type="text",
            payload={"actual_output": "实际输出"},
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert "expected_output" in result.error


class TestTextMatchEvaluatorBoundaryCases:
    """边界测试 - 边界值"""

    @staticmethod
    def test_very_long_input_handled():
        """超长输入应被正确处理"""
        target = TextMatchEvaluator(client=None)
        long_text = "测试" * 1000
        request = EvaluationSchema(
            id="text_bound_001",
            type="text",
            payload={
                "actual_output": long_text,
                "expected_output": long_text,
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0

    @staticmethod
    def test_unicode_chinese_input_handled():
        """中文Unicode输入应被正确处理"""
        target = TextMatchEvaluator(client=None)
        request = EvaluationSchema(
            id="text_bound_002",
            type="text",
            payload={
                "actual_output": "你好，世界！",
                "expected_output": "你好，世界！",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0

    @staticmethod
    def test_completely_different_output_gets_low_score(monkeypatch):
        """完全不同输出应返回低分"""
        from src.domain.evaluators.metadata import TextMetadata

        monkeypatch.setattr(TextMetadata, "tone", "", raising=False)

        target = TextMatchEvaluator(client=None)
        request = EvaluationSchema(
            id="text_bound_003",
            type="text",
            payload={
                "actual_output": "xyz123abc",
                "expected_output": "完全不同的答案内容",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score < 0.5
