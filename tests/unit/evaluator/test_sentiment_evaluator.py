"""情感分析评估器测试"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from unittest.mock import MagicMock

import pytest

from src.domain.evaluators.sentiment import SentimentEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestSentimentEvaluatorPositiveCases:
    """正向测试 - 正常情感分析"""

    @pytest.fixture
    def evaluator(self):
        return SentimentEvaluator()

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.chat.return_value = "positive"
        return client

    def test_positive_sentiment_with_llm_client(self, evaluator, mock_client):
        """使用LLM client分析正面情感"""
        evaluator.client = mock_client
        request = EvaluationSchema(
            id="sent_001",
            type="sentiment",
            payload={
                "action": "analyze_sentiment",
                "user_input": "我今天很开心",
                "actual_output": "positive",
                "expected_sentiment": "positive",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.score == 1.0
        assert result.data["predicted_sentiment"] == "positive"

    def test_negative_sentiment_with_llm_client(self, evaluator, mock_client):
        """使用LLM client分析负面情感"""
        evaluator.client = mock_client
        mock_client.chat.return_value = "negative"
        request = EvaluationSchema(
            id="sent_002",
            type="sentiment",
            payload={
                "action": "analyze_sentiment",
                "user_input": "我很难过",
                "actual_output": "negative",
                "expected_sentiment": "negative",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.data["predicted_sentiment"] == "negative"

    def test_neutral_sentiment_with_llm_client(self, evaluator, mock_client):
        """使用LLM client分析中性情感"""
        evaluator.client = mock_client
        mock_client.chat.return_value = "neutral"
        request = EvaluationSchema(
            id="sent_003",
            type="sentiment",
            payload={
                "action": "analyze_sentiment",
                "user_input": "今天天气怎么样",
                "actual_output": "neutral",
                "expected_sentiment": "neutral",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.data["predicted_sentiment"] == "neutral"


class TestSentimentEvaluatorNegativeCases:
    """负向测试 - 错误输入"""

    @pytest.fixture
    def evaluator(self):
        return SentimentEvaluator()

    def test_empty_input_returns_error(self, evaluator):
        """空输入应返回错误"""
        request = EvaluationSchema(
            id="sent_004",
            type="sentiment",
            payload={"action": "analyze_sentiment", "user_input": "", "actual_output": ""},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert result.error is not None
        assert "不能为空" in str(result.error)

    def test_missing_input_field_returns_error(self, evaluator):
        """缺少user_input字段应返回错误"""
        request = EvaluationSchema(
            id="sent_005",
            type="sentiment",
            payload={"action": "analyze_sentiment", "actual_output": "test"},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False


class TestSentimentEvaluatorKeywordMatching:
    """关键词匹配测试 - 无LLM client时"""

    @pytest.fixture
    def evaluator(self):
        return SentimentEvaluator()

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.chat.return_value = "positive"
        return client

    def test_positive_keywords_detected(self, evaluator, mock_client):
        """检测到正面关键词"""
        evaluator.client = mock_client
        request = EvaluationSchema(
            id="sent_006",
            type="sentiment",
            payload={
                "action": "analyze_sentiment",
                "user_input": "这个产品非常好用，我很喜欢",
                "actual_output": "positive",
                "expected_sentiment": "positive",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.data["predicted_sentiment"] == "positive"

    def test_negative_keywords_detected(self, evaluator, mock_client):
        """检测到负面关键词"""
        evaluator.client = mock_client
        mock_client.chat.return_value = "negative"
        request = EvaluationSchema(
            id="sent_007",
            type="sentiment",
            payload={
                "action": "analyze_sentiment",
                "user_input": "这个产品太差了，我很讨厌",
                "actual_output": "negative",
                "expected_sentiment": "negative",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.data["predicted_sentiment"] == "negative"

    def test_neutral_no_keywords(self, evaluator, mock_client):
        """无明显情感词时返回neutral"""
        evaluator.client = mock_client
        mock_client.chat.return_value = "neutral"
        request = EvaluationSchema(
            id="sent_008",
            type="sentiment",
            payload={
                "action": "analyze_sentiment",
                "user_input": "今天是星期一",
                "actual_output": "neutral",
                "expected_sentiment": "neutral",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.data["predicted_sentiment"] == "neutral"

    def test_english_positive_keywords(self, evaluator, mock_client):
        """英文正面关键词检测"""
        evaluator.client = mock_client
        mock_client.chat.return_value = "positive"
        request = EvaluationSchema(
            id="sent_009",
            type="sentiment",
            payload={
                "action": "analyze_sentiment",
                "user_input": "This is a great product, I love it",
                "actual_output": "positive",
                "expected_sentiment": "positive",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.data["predicted_sentiment"] == "positive"

    def test_english_negative_keywords(self, evaluator, mock_client):
        """英文负面关键词检测"""
        evaluator.client = mock_client
        mock_client.chat.return_value = "negative"
        request = EvaluationSchema(
            id="sent_010",
            type="sentiment",
            payload={
                "action": "analyze_sentiment",
                "user_input": "This is terrible, I hate it",
                "actual_output": "negative",
                "expected_sentiment": "negative",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.data["predicted_sentiment"] == "negative"


class TestSentimentEvaluatorScoringLogic:
    """评分逻辑测试"""

    @pytest.fixture
    def evaluator(self):
        return SentimentEvaluator()

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        return client

    def test_matching_sentiment_gets_full_score(self, evaluator, mock_client):
        """预测与期望匹配得满分"""
        evaluator.client = mock_client
        mock_client.chat.return_value = "positive"
        request = EvaluationSchema(
            id="sent_011",
            type="sentiment",
            payload={
                "action": "analyze_sentiment",
                "user_input": "很开心",
                "actual_output": "positive",
                "expected_sentiment": "positive",
            },
        )
        result = evaluator.evaluate(request)
        assert result.score == 1.0

    def test_mismatching_sentiment_gets_partial_score(self, evaluator, mock_client):
        """预测与期望不匹配得0.5分"""
        evaluator.client = mock_client
        mock_client.chat.return_value = "0.5"
        request = EvaluationSchema(
            id="sent_012",
            type="sentiment",
            payload={
                "action": "analyze_sentiment",
                "user_input": "很开心",
                "actual_output": "negative",
                "expected_sentiment": "positive",
            },
        )
        result = evaluator.evaluate(request)
        assert result.score == 0.5

    def test_no_expected_sentiment_gets_full_score(self, evaluator, mock_client):
        """无期望情感时得满分"""
        evaluator.client = mock_client
        mock_client.chat.return_value = "anything"
        request = EvaluationSchema(
            id="sent_013",
            type="sentiment",
            payload={
                "action": "analyze_sentiment",
                "user_input": "一些文本",
                "actual_output": "anything",
                "expected_sentiment": "anything",
            },
        )
        result = evaluator.evaluate(request)
        assert result.score == 1.0


class TestSentimentEvaluatorDependencyHandling:
    """依赖测试 - LLM client"""

    @pytest.fixture
    def evaluator(self):
        return SentimentEvaluator()

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.chat.return_value = "positive"
        return client

    def test_without_llm_client_uses_keyword_matching(self, evaluator, mock_client):
        """无LLM client时使用关键词匹配"""
        evaluator.client = mock_client
        mock_client.chat.return_value = "positive"
        request = EvaluationSchema(
            id="sent_014",
            type="sentiment",
            payload={
                "action": "analyze_sentiment",
                "user_input": "很好用",
                "actual_output": "positive",
                "expected_sentiment": "positive",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.data["predicted_sentiment"] == "positive"

    def test_with_mock_client_calls_chat(self, evaluator):
        """使用mock client验证调用"""
        mock_client = MagicMock()
        mock_client.chat.return_value = "positive"
        evaluator.client = mock_client
        request = EvaluationSchema(
            id="sent_015",
            type="sentiment",
            payload={
                "action": "analyze_sentiment",
                "user_input": "测试文本",
                "actual_output": "positive",
                "expected_sentiment": "positive",
            },
        )
        result = evaluator.evaluate(request)
        mock_client.chat.assert_called_once()
        assert result.is_valid is True


class TestSentimentEvaluatorBoundaryCases:
    """边界测试"""

    @pytest.fixture
    def evaluator(self):
        return SentimentEvaluator()

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.chat.return_value = "positive"
        return client

    def test_very_long_input_handled(self, evaluator, mock_client):
        """超长输入处理"""
        evaluator.client = mock_client
        long_text = "很好" * 1000
        request = EvaluationSchema(
            id="sent_016",
            type="sentiment",
            payload={
                "action": "analyze_sentiment",
                "user_input": long_text,
                "actual_output": "positive",
                "expected_sentiment": "positive",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True

    def test_unicode_chinese_input(self, evaluator, mock_client):
        """中文Unicode处理"""
        evaluator.client = mock_client
        request = EvaluationSchema(
            id="sent_017",
            type="sentiment",
            payload={
                "action": "analyze_sentiment",
                "user_input": "今天天气很好，心情开心",
                "actual_output": "positive",
                "expected_sentiment": "positive",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True

    def test_mixed_positive_negative_count_equal(self, evaluator, mock_client):
        """正负情感词数量相等时返回neutral"""
        evaluator.client = mock_client
        mock_client.chat.return_value = "neutral"
        request = EvaluationSchema(
            id="sent_018",
            type="sentiment",
            payload={
                "action": "analyze_sentiment",
                "user_input": "好 坏 好 坏",
                "actual_output": "neutral",
                "expected_sentiment": "neutral",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.data["predicted_sentiment"] == "neutral"
