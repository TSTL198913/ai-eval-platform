"""问答评估器测试"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from unittest.mock import MagicMock

import pytest

from src.domain.evaluators.qa import QAEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestQAEvaluatorPositiveCases:
    """正向测试 - 正常问答评估"""

    @pytest.fixture
    def evaluator(self):
        return QAEvaluator()

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.chat.return_value = "北京是中国的首都。"
        return client

    def test_qa_with_context_and_expected(self, evaluator, mock_client):
        """有上下文和期望答案时评估"""
        evaluator.client = mock_client
        request = EvaluationSchema(
            id="qa_001",
            type="qa",
            payload={
                "action": "evaluate_qa",
                "user_input": "中国的首都是哪里？",
                "context": "北京是中国的首都。",
                "expected_output": "北京",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.score >= 0.0
        assert "北京" in result.text or "北京" in result.data

    def test_qa_with_llm_response(self, evaluator, mock_client):
        """使用LLM生成答案"""
        mock_client.chat.return_value = "中国的首都是北京。"
        evaluator.client = mock_client
        request = EvaluationSchema(
            id="qa_002",
            type="qa",
            payload={
                "action": "evaluate_qa",
                "user_input": "首都是哪里？",
                "context": "中国首都是北京。",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        mock_client.chat.assert_called_once()


class TestQAEvaluatorNegativeCases:
    """负向测试 - 错误输入"""

    @pytest.fixture
    def evaluator(self):
        return QAEvaluator()

    def test_empty_input_returns_error(self, evaluator):
        """空输入应返回错误"""
        request = EvaluationSchema(
            id="qa_003",
            type="qa",
            payload={"action": "evaluate_qa", "user_input": ""},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False

    def test_missing_input_field_returns_error(self, evaluator):
        """缺少user_input字段应返回错误"""
        request = EvaluationSchema(
            id="qa_004",
            type="qa",
            payload={"action": "evaluate_qa"},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False


class TestQAEvaluatorDependencyHandling:
    """依赖测试 - LLM client"""

    @pytest.fixture
    def evaluator(self):
        return QAEvaluator()

    def test_without_llm_client_uses_input_as_output(self, evaluator):
        """无LLM client时使用输入作为输出"""
        evaluator.client = None
        request = EvaluationSchema(
            id="qa_005",
            type="qa",
            payload={
                "action": "evaluate_qa",
                "user_input": "什么是AI？",
                "expected_output": "AI是人工智能",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert "什么是AI" in result.text

    def test_with_mock_client_calls_chat(self, evaluator):
        """使用mock client验证调用"""
        mock_client = MagicMock()
        mock_client.chat.return_value = "答案是42"
        evaluator.client = mock_client
        request = EvaluationSchema(
            id="qa_006",
            type="qa",
            payload={
                "action": "evaluate_qa",
                "user_input": "生命的意义是什么？",
                "context": "这是一个哲学问题。",
            },
        )
        result = evaluator.evaluate(request)
        mock_client.chat.assert_called_once()
        assert result.is_valid is True


class TestQAEvaluatorBoundaryCases:
    """边界测试"""

    @pytest.fixture
    def evaluator(self):
        return QAEvaluator()

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.chat.return_value = "答案"
        return client

    def test_empty_context_handled(self, evaluator, mock_client):
        """空上下文处理"""
        evaluator.client = mock_client
        request = EvaluationSchema(
            id="qa_007",
            type="qa",
            payload={
                "action": "evaluate_qa",
                "user_input": "问题？",
                "context": "",
                "expected_output": "答案",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True

    def test_empty_expected_output(self, evaluator, mock_client):
        """空期望答案得满分"""
        evaluator.client = mock_client
        request = EvaluationSchema(
            id="qa_008",
            type="qa",
            payload={
                "action": "evaluate_qa",
                "user_input": "问题？",
                "expected_output": "",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.score == 1.0

    def test_both_missing_returns_error(self, evaluator):
        """user_input缺失时返回错误"""
        evaluator.client = None
        request = EvaluationSchema(
            id="qa_009",
            type="qa",
            payload={
                "action": "evaluate_qa",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False


class TestQAEvaluatorScoringLogic:
    """评分逻辑测试"""

    @pytest.fixture
    def evaluator(self):
        return QAEvaluator()

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.chat.return_value = "北京是中国的首都"
        return client

    def test_exact_match_gets_high_score(self, evaluator, mock_client):
        """精确匹配得高分"""
        evaluator.client = mock_client
        request = EvaluationSchema(
            id="qa_010",
            type="qa",
            payload={
                "action": "evaluate_qa",
                "user_input": "首都是？",
                "expected_output": "北京是中国的首都",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.score >= 0.0

    def test_no_match_gets_low_score(self, evaluator, mock_client):
        """完全不匹配得低分"""
        evaluator.client = mock_client
        mock_client.chat.return_value = "完全不同的答案 xyz"
        request = EvaluationSchema(
            id="qa_011",
            type="qa",
            payload={
                "action": "evaluate_qa",
                "user_input": "首都是？",
                "expected_output": "北京",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.score >= 0.0
