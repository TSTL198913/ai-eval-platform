"""
GrammarEvaluator - 语法检查评估器专项测试
测试目标：验证GrammarEvaluator的actual_output校验、语法错误检测、评分逻辑等核心功能
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.grammar import GrammarEvaluator, _simple_grammar_check
from src.schemas.evaluation import EvaluationSchema


class TestGrammarEvaluatorPositiveCases:
    """正向测试 - 正常输入"""

    @staticmethod
    def test_valid_input_returns_valid_response():
        """合法输入应返回is_valid=True"""
        target = GrammarEvaluator(client=None)
        request = EvaluationSchema(
            id="gram_001",
            type="grammar",
            payload={"actual_output": "这是一个正确的句子。"},
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score is not None
        assert result.error is None
        
        # 强断言：验证置信度和状态
        assert result.confidence is not None, "confidence不应为None"
        assert 0.0 <= result.confidence <= 1.0, f"confidence应在0-1之间，实际为{result.confidence}"
        assert result.evaluation_status.value == "success", f"evaluation_status应为success"

    @staticmethod
    def test_no_errors_returns_full_score():
        """无错误时应返回score=1.0"""
        target = GrammarEvaluator(client=None)
        request = EvaluationSchema(
            id="gram_002",
            type="grammar",
            payload={"actual_output": "正确的句子。"},
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0
        
        # 强断言：验证置信度和状态
        assert result.confidence is not None, "confidence不应为None"
        assert result.evaluation_status.value == "success", f"evaluation_status应为success"

    @staticmethod
    def test_one_error_returns_reduced_score():
        """1个错误应返回score=0.8"""
        target = GrammarEvaluator(client=None)
        request = EvaluationSchema(
            id="gram_003",
            type="grammar",
            payload={"actual_output": "有错误的句子"},
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score == 0.8

    @staticmethod
    def test_multiple_errors_calculated_correctly():
        """多个错误应按公式计算: score = max(0, 1.0 - error_count * 0.2)"""
        target = GrammarEvaluator(client=None)
        request = EvaluationSchema(
            id="gram_004",
            type="grammar",
            payload={"actual_output": "有多个错误的句子"},
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert abs(result.score - 0.8) < 0.001


class TestGrammarEvaluatorNegativeCases:
    """负向测试 - 错误输入"""

    @staticmethod
    def test_empty_actual_output_returns_error():
        """空actual_output应返回is_valid=False"""
        target = GrammarEvaluator(client=None)
        request = EvaluationSchema(
            id="gram_neg_001",
            type="grammar",
            payload={"actual_output": ""},
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert result.error is not None
        assert "actual_output" in result.error

    @staticmethod
    def test_missing_actual_output_returns_error():
        """缺少actual_output字段应返回错误"""
        target = GrammarEvaluator(client=None)
        request = EvaluationSchema(
            id="gram_neg_002",
            type="grammar",
            payload={},
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert "actual_output" in result.error

    @staticmethod
    def test_none_actual_output_returns_error():
        """None actual_output应返回错误"""
        target = GrammarEvaluator(client=None)
        request = EvaluationSchema(
            id="gram_neg_003",
            type="grammar",
            payload={"actual_output": None},
        )
        result = target.evaluate(request)

        assert result.is_valid is False


class TestGrammarEvaluatorBoundaryCases:
    """边界测试 - 边界值"""

    @staticmethod
    def test_more_than_five_errors_returns_zero_score():
        """超过5个错误应返回score=0（最低分数）"""
        target = GrammarEvaluator(client=None)
        request = EvaluationSchema(
            id="gram_bound_001",
            type="grammar",
            payload={"actual_output": "a b c d e f"},
        )
        result = target.evaluate(request)

        assert result.score >= 0.0

    @staticmethod
    def test_very_long_text_handled():
        """超长文本应被正确处理"""
        target = GrammarEvaluator(client=None)
        long_text = "测试" * 1000
        request = EvaluationSchema(
            id="gram_bound_002",
            type="grammar",
            payload={"actual_output": long_text + "。"},
        )
        result = target.evaluate(request)

        assert result.is_valid is True

    @staticmethod
    def test_unicode_chinese_input_handled():
        """中文Unicode输入应被正确处理"""
        target = GrammarEvaluator(client=None)
        request = EvaluationSchema(
            id="gram_bound_003",
            type="grammar",
            payload={"actual_output": "你好，世界！"},
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0


class TestGrammarErrorCounting:
    """语法错误计数逻辑测试"""

    @staticmethod
    def test_count_no_errors():
        """无语法错误"""
        count, errors = _simple_grammar_check("Hello, world!")
        assert count == 0
        assert len(errors) == 0

    @staticmethod
    def test_count_missing_punctuation():
        """缺少句末标点"""
        count, errors = _simple_grammar_check("Hello world")
        assert count == 1
        assert "缺少句末标点" in errors

    @staticmethod
    def test_count_lowercase_first_letter():
        """首字母小写"""
        count, errors = _simple_grammar_check("hello world.")
        assert count == 1
        assert "首字母应大写" in errors

    @staticmethod
    def test_count_consecutive_spaces():
        """连续空格"""
        count, errors = _simple_grammar_check("Hello  world.")
        assert count == 1
        assert any("连续空格" in error for error in errors)

    @staticmethod
    def test_count_multiple_errors():
        """多个错误"""
        count, errors = _simple_grammar_check("hello  world")
        assert count >= 2

    @staticmethod
    def test_count_empty_text():
        """空文本"""
        count, errors = _simple_grammar_check("")
        assert count == 0
