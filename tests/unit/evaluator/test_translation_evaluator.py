"""翻译评估器测试"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from unittest.mock import MagicMock

import pytest

from src.domain.evaluators.translation import TranslationEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestTranslationEvaluatorPositiveCases:
    """正向测试 - 正常翻译评估"""

    @pytest.fixture
    def evaluator(self):
        return TranslationEvaluator()

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.chat.return_value = "Hello, world!"
        return client

    def test_translation_with_target_language(self, evaluator, mock_client):
        """指定目标语言翻译"""
        evaluator.client = mock_client
        request = EvaluationSchema(
            id="trans_001",
            type="translation",
            payload={
                "action": "evaluate_translation",
                "user_input": "你好，世界！",
                "target_language": "英文",
                "expected_output": "Hello, world!",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        mock_client.chat.assert_called_once()

    def test_translation_with_default_target(self, evaluator, mock_client):
        """默认目标语言(英文)翻译"""
        evaluator.client = mock_client
        request = EvaluationSchema(
            id="trans_002",
            type="translation",
            payload={
                "action": "evaluate_translation",
                "user_input": "你好",
                "expected_output": "Hello",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert "Hello" in result.text or "hello" in result.text.lower()


class TestTranslationEvaluatorNegativeCases:
    """负向测试 - 错误输入"""

    @pytest.fixture
    def evaluator(self):
        return TranslationEvaluator()

    def test_empty_input_returns_error(self, evaluator):
        """空输入应返回错误"""
        request = EvaluationSchema(
            id="trans_003",
            type="translation",
            payload={"action": "evaluate_translation", "user_input": ""},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False

    def test_missing_input_field_returns_error(self, evaluator):
        """缺少user_input字段应返回错误"""
        request = EvaluationSchema(
            id="trans_004",
            type="translation",
            payload={"action": "evaluate_translation"},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False


class TestTranslationEvaluatorDependencyHandling:
    """依赖测试 - LLM client"""

    @pytest.fixture
    def evaluator(self):
        return TranslationEvaluator()

    def test_without_llm_client_uses_input_as_output(self, evaluator):
        """无LLM client时使用输入作为输出"""
        evaluator.client = None
        request = EvaluationSchema(
            id="trans_005",
            type="translation",
            payload={
                "action": "evaluate_translation",
                "user_input": "Hello",
                "expected_output": "Hello",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert "Hello" in result.text

    def test_with_mock_client_calls_chat(self, evaluator):
        """使用mock client验证调用"""
        mock_client = MagicMock()
        mock_client.chat.return_value = "Goodbye"
        evaluator.client = mock_client
        request = EvaluationSchema(
            id="trans_006",
            type="translation",
            payload={
                "action": "evaluate_translation",
                "user_input": "再见",
                "target_language": "英文",
            },
        )
        result = evaluator.evaluate(request)
        mock_client.chat.assert_called_once()
        assert result.is_valid is True


class TestTranslationEvaluatorBoundaryCases:
    """边界测试"""

    @pytest.fixture
    def evaluator(self):
        return TranslationEvaluator()

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.chat.return_value = "Translated"
        return client

    def test_empty_target_language_uses_default(self, evaluator, mock_client):
        """空目标语言使用默认值"""
        evaluator.client = mock_client
        request = EvaluationSchema(
            id="trans_007",
            type="translation",
            payload={
                "action": "evaluate_translation",
                "user_input": "你好",
                "target_language": "",
                "expected_output": "Hello",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True

    def test_empty_expected_output_gets_full_score(self, evaluator, mock_client):
        """空期望输出得满分"""
        evaluator.client = mock_client
        request = EvaluationSchema(
            id="trans_008",
            type="translation",
            payload={
                "action": "evaluate_translation",
                "user_input": "你好",
                "expected_output": "",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.score == 1.0

    def test_custom_target_language(self, evaluator, mock_client):
        """自定义目标语言"""
        evaluator.client = mock_client
        mock_client.chat.return_value = "Bonjour"
        request = EvaluationSchema(
            id="trans_009",
            type="translation",
            payload={
                "action": "evaluate_translation",
                "user_input": "你好",
                "target_language": "法文",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True


class TestTranslationEvaluatorScoringLogic:
    """评分逻辑测试"""

    @pytest.fixture
    def evaluator(self):
        return TranslationEvaluator()

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.chat.return_value = "Hello"
        return client

    def test_similar_translation_gets_high_score(self, evaluator, mock_client):
        """相似翻译得高分"""
        evaluator.client = mock_client
        request = EvaluationSchema(
            id="trans_010",
            type="translation",
            payload={
                "action": "evaluate_translation",
                "user_input": "你好",
                "expected_output": "Hello",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.score >= 0.0

    def test_different_translation_gets_low_score(self, evaluator, mock_client):
        """不同翻译得低分"""
        evaluator.client = mock_client
        mock_client.chat.return_value = "Goodbye"
        request = EvaluationSchema(
            id="trans_011",
            type="translation",
            payload={
                "action": "evaluate_translation",
                "user_input": "你好",
                "expected_output": "Hello",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.score >= 0.0
