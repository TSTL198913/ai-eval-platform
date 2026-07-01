"""问答评估器测试"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.qa import QAEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestQAEvaluatorPositiveCases:
    """正向测试 - 正常问答评估"""

    @staticmethod
    def test_qa_with_expected_output_returns_exact_score():
        """有expected_output时应返回精确分数"""
        mock_client = MagicMock()
        mock_client.chat.return_value = "0.85"

        evaluator = QAEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="qa_001",
            type="qa",
            payload={
                "user_input": "中国的首都是哪里？",
                "actual_output": "北京是中国的首都。",
                "expected_output": "北京",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.score == pytest.approx(0.85, abs=0.01)
        mock_client.chat.assert_called_once()

    @staticmethod
    def test_exact_match_gets_high_score():
        """精确匹配得高分"""
        mock_client = MagicMock()
        mock_client.chat.return_value = "1.0"

        evaluator = QAEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="qa_002",
            type="qa",
            payload={
                "user_input": "中国的首都是哪里？",
                "actual_output": "北京是中国的首都",
                "expected_output": "北京是中国的首都",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.score == 1.0

    @staticmethod
    def test_llm_called_with_correct_prompt():
        """验证LLM被调用时传递正确的Prompt内容"""
        mock_client = MagicMock()
        mock_client.chat.return_value = "0.8"

        evaluator = QAEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="qa_003",
            type="qa",
            payload={
                "user_input": "什么是机器学习？",
                "actual_output": "机器学习是AI的分支",
                "expected_output": "机器学习是人工智能的一个分支",
            },
        )
        evaluator.evaluate(request)
        
        mock_client.chat.assert_called_once()
        call_args = mock_client.chat.call_args
        prompt = call_args[0][0] if call_args[0] else call_args[1].get("user_input", "")
        assert "机器学习是AI的分支" in prompt
        assert "机器学习是人工智能的一个分支" in prompt


class TestQAEvaluatorNegativeCases:
    """负向测试 - 错误输入"""

    @staticmethod
    def test_empty_actual_output_uses_empty_string():
        """空actual_output时使用空字符串进行评估"""
        mock_client = MagicMock()
        mock_client.chat.return_value = "0.5"
        evaluator = QAEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="qa_neg_001",
            type="qa",
            payload={"user_input": "问题", "actual_output": "", "expected_output": "答案"},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True

    @staticmethod
    def test_missing_actual_output_returns_error():
        """缺少actual_output字段应返回错误"""
        mock_client = MagicMock()
        evaluator = QAEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="qa_neg_002",
            type="qa",
            payload={"user_input": "问题", "expected_output": "答案"},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert result.error is not None

    @staticmethod
    def test_missing_expected_output_returns_error():
        """缺少expected_output字段应返回错误"""
        mock_client = MagicMock()
        evaluator = QAEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="qa_neg_003",
            type="qa",
            payload={"user_input": "问题", "actual_output": "答案"},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert result.error is not None
        assert "expected_output" in result.error

    @staticmethod
    def test_missing_user_input_returns_error():
        """缺少user_input字段应返回错误"""
        mock_client = MagicMock()
        evaluator = QAEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="qa_neg_004",
            type="qa",
            payload={"actual_output": "答案", "expected_output": "答案"},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert result.error is not None


class TestQAEvaluatorBoundaryCases:
    """边界测试"""

    @staticmethod
    def test_no_match_gets_low_score():
        """完全不匹配得低分"""
        mock_client = MagicMock()
        mock_client.chat.return_value = "0.15"

        evaluator = QAEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="qa_bound_001",
            type="qa",
            payload={
                "user_input": "中国的首都是哪里？",
                "actual_output": "完全不同的答案 xyz",
                "expected_output": "北京",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.score == pytest.approx(0.15, abs=0.01)

    @staticmethod
    def test_partial_match_gets_exact_score():
        """部分匹配得精确分数"""
        mock_client = MagicMock()
        mock_client.chat.return_value = "0.65"

        evaluator = QAEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="qa_bound_002",
            type="qa",
            payload={
                "user_input": "中国的首都是哪里？",
                "actual_output": "中国首都是北京",
                "expected_output": "北京是中国的首都",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.score == pytest.approx(0.65, abs=0.01)

    @staticmethod
    def test_long_text_input_handled():
        """长文本输入应被正确处理"""
        mock_client = MagicMock()
        mock_client.chat.return_value = "0.9"
        
        long_text = "测试" * 500
        evaluator = QAEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="qa_bound_003",
            type="qa",
            payload={
                "user_input": "问题",
                "actual_output": long_text,
                "expected_output": long_text,
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.score == pytest.approx(0.9, abs=0.01)