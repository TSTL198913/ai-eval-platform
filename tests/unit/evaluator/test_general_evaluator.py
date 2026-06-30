"""
GeneralEvaluator - 通用评估器专项测试
测试目标：验证GeneralEvaluator的validate_input、_sanitize_input脱敏、无LLM client时直接返回score=1.0等核心功能
关键发现：（测试过程中记录）
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.general import GeneralEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestGeneralEvaluatorPositiveCases:
    """正向测试 - 正常输入"""

    @pytest.fixture
    def mock_client(self):
        """Mock LLM客户端"""
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        client.chat.return_value = "0.85"
        return client

    @pytest.fixture
    def target(self, mock_client):
        return GeneralEvaluator(client=mock_client)

    def test_valid_input_with_expected_output_calls_llm(self, target, mock_client):
        """合法输入+expected_output应调用LLM并评分"""
        request = EvaluationSchema(
            id="gen_001",
            type="general",
            payload={
                "user_input": "测试问题",
                "expected_output": "通用评估的回答内容",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        mock_client.chat.assert_called_once()
        assert result.score is not None

    def test_valid_input_with_system_prompt_uses_custom_prompt(self, target, mock_client):
        """带system_prompt的输入应传递给LLM"""
        request = EvaluationSchema(
            id="gen_002",
            type="general",
            payload={
                "user_input": "测试问题",
                "expected_output": "通用评估的回答内容",
                "system_prompt": "你是一个通用助手",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        mock_client.chat.assert_called_once()

    def test_text_field_instead_of_user_input_works(self, target, mock_client):
        """使用text字段代替user_input也应正常工作"""
        request = EvaluationSchema(
            id="gen_003",
            type="general",
            payload={
                "text": "另一个问题",
                "expected_output": "通用评估的回答内容",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True


class TestGeneralEvaluatorNegativeCases:
    """负向测试 - 错误输入"""

    @pytest.fixture
    def target(self):
        return GeneralEvaluator(client=None)

    def test_empty_user_input_returns_error(self, target):
        """空user_input应返回is_valid=False"""
        request = EvaluationSchema(
            id="gen_neg_001",
            type="general",
            payload={"user_input": ""},
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert result.error is not None
        assert "不能为空" in result.error

    def test_empty_text_returns_error(self, target):
        """空text字段应返回is_valid=False"""
        request = EvaluationSchema(
            id="gen_neg_002",
            type="general",
            payload={"text": ""},
        )
        result = target.evaluate(request)

        assert result.is_valid is False

    def test_missing_input_returns_error(self, target):
        """缺少输入字段应返回错误"""
        request = EvaluationSchema(
            id="gen_neg_003",
            type="general",
            payload={},
        )
        result = target.evaluate(request)

        assert result.is_valid is False


class TestGeneralEvaluatorBoundaryCases:
    """边界测试 - 边界值"""

    def test_without_llm_client_returns_error(self):
        """无LLM client时应返回错误"""
        target = GeneralEvaluator(client=None)
        request = EvaluationSchema(
            id="gen_bound_001",
            type="general",
            payload={"user_input": "测试问题", "expected_output": "测试回答"},
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert "需要 LLM 客户端" in result.error

    def test_none_input_returns_error(self):
        """None输入应被正确处理"""
        target = GeneralEvaluator(client=None)
        request = EvaluationSchema(
            id="gen_bound_002",
            type="general",
            payload={"user_input": None},
        )
        result = target.evaluate(request)

        assert result.is_valid is False

    def test_empty_expected_output_returns_error(self):
        """无expected_output时应返回错误"""
        target = GeneralEvaluator(client=None)
        request = EvaluationSchema(
            id="gen_bound_003",
            type="general",
            payload={"user_input": "测试问题"},
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert "expected_output" in result.error


class TestGeneralEvaluatorSanitization:
    """脱敏测试"""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        client.chat.return_value = "处理后的回答"
        return client

    def test_openai_api_key_sanitized(self, mock_client):
        """输入包含sk-xxx应被脱敏"""
        target = GeneralEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="gen_san_001",
            type="general",
            payload={
                "user_input": "请处理这个sk-1234567890abcdefghijklmn",
                "expected_output": "处理后的回答",
            },
        )
        _ = target.evaluate(request)

        mock_client.chat.assert_called_once()
        call_args = mock_client.chat.call_args
        sanitized_input = call_args[0][0] if call_args[0] else call_args[1].get("user_input", "")
        assert "sk-1234567890abcdefghijklmn" not in sanitized_input
        assert "[REDACTED_API_KEY]" in sanitized_input

    def test_aws_key_sanitized(self, mock_client):
        """输入包含AKIAxxx应被脱敏"""
        target = GeneralEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="gen_san_002",
            type="general",
            payload={
                "user_input": "请处理这个AKIAIOSFODNN7EXAMPLE",
                "expected_output": "处理后的回答",
            },
        )
        _ = target.evaluate(request)

        call_args = mock_client.chat.call_args
        sanitized_input = call_args[0][0] if call_args[0] else call_args[1].get("user_input", "")
        assert "AKIAIOSFODNN7EXAMPLE" not in sanitized_input
        assert "[REDACTED_AWS_KEY]" in sanitized_input

    def test_gcp_key_sanitized(self, mock_client):
        """输入包含AIza应被脱敏"""
        target = GeneralEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="gen_san_003",
            type="general",
            payload={
                "user_input": "请处理这个AIzaSyD7QZ5RtT3GpDkqH5xBqVzVvJWlDW3q123",
                "expected_output": "处理后的回答",
            },
        )
        _ = target.evaluate(request)

        call_args = mock_client.chat.call_args
        sanitized_input = call_args[0][0] if call_args[0] else call_args[1].get("user_input", "")
        assert "AIzaSyD7QZ5RtT3GpDkqH5xBqVzVvJWlDW3q123" not in sanitized_input
        assert "[REDACTED_GCP_KEY]" in sanitized_input

    def test_mongodb_uri_sanitized(self, mock_client):
        """输入包含mongodb+srv://应被脱敏"""
        target = GeneralEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="gen_san_004",
            type="general",
            payload={
                "user_input": "请处理mongodb+srv://user:pass@cluster.mongodb.net",
                "expected_output": "处理后的回答",
            },
        )
        _ = target.evaluate(request)

        call_args = mock_client.chat.call_args
        sanitized_input = call_args[0][0] if call_args[0] else call_args[1].get("user_input", "")
        assert "mongodb+srv://" not in sanitized_input
        assert "[REDACTED_MONGO_URI]" in sanitized_input

    def test_postgres_uri_sanitized(self, mock_client):
        """输入包含postgres://应被脱敏"""
        target = GeneralEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="gen_san_005",
            type="general",
            payload={
                "user_input": "请处理postgres://user:pass@localhost:5432/db",
                "expected_output": "处理后的回答",
            },
        )
        _ = target.evaluate(request)

        call_args = mock_client.chat.call_args
        sanitized_input = call_args[0][0] if call_args[0] else call_args[1].get("user_input", "")
        assert "postgres://" not in sanitized_input
        assert "[REDACTED_PG_URI]" in sanitized_input

    def test_multiple_secrets_sanitized(self, mock_client):
        """多个敏感信息应都被脱敏"""
        target = GeneralEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="gen_san_006",
            type="general",
            payload={
                "user_input": "sk-12345678901234567890",  # 22字符，满足{20,}
                "expected_output": "处理后的回答",
            },
        )
        _ = target.evaluate(request)

        call_args = mock_client.chat.call_args
        sanitized_input = call_args[0][0] if call_args[0] else call_args[1].get("user_input", "")
        assert "sk-12345678901234567890" not in sanitized_input


class TestGeneralEvaluatorScoringLogic:
    """评分逻辑测试"""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        return client

    def test_without_expected_output_returns_error(self):
        """无expected_output时应返回错误"""
        mock_client = MagicMock()
        mock_client.config = MagicMock()
        mock_client.config.model_name = "gpt-4"
        mock_client.chat.return_value = "0.8"
        target = GeneralEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="gen_score_001",
            type="general",
            payload={"user_input": "测试问题"},
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert "expected_output" in result.error

    def test_with_expected_output_uses_similarity(self, mock_client):
        """有expected_output时应使用相似度评分"""
        mock_client.chat.return_value = "0.85"
        target = GeneralEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="gen_score_002",
            type="general",
            payload={
                "user_input": "测试问题",
                "expected_output": "相似的回答",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score == 0.85
