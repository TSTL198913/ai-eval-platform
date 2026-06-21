"""
TextMatchEvaluator - 文本匹配评估器专项测试
测试目标：验证TextMatchEvaluator的validate_input、require_client、client.chat、score_text_similarity等核心功能
关键发现：（测试过程中记录）
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.text import TextMatchEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestTextMatchEvaluatorPositiveCases:
    """正向测试 - 正常输入"""

    @pytest.fixture
    def mock_client(self):
        """Mock LLM客户端"""
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        client.chat.return_value = "AI是人工智能的缩写"
        return client

    @pytest.fixture
    def target(self, mock_client):
        return TextMatchEvaluator(client=mock_client)

    def test_valid_input_with_expected_output_returns_valid_response(self, target, mock_client):
        """合法输入+expected_output应返回is_valid=True, score基于相似度"""
        request = EvaluationSchema(
            id="text_001",
            type="text",
            payload={
                "user_input": "什么是AI？",
                "expected_output": "AI是人工智能的缩写",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score is not None
        assert result.score >= 0.0
        assert result.score <= 1.0
        mock_client.chat.assert_called_once()

    def test_valid_input_with_system_prompt_uses_custom_prompt(self, target, mock_client):
        """带system_prompt的输入应使用自定义提示词"""
        # mock返回与expected_output相同的内容，以获得高分
        mock_client.chat.return_value = "机器学习是AI的一个分支"
        request = EvaluationSchema(
            id="text_002",
            type="text",
            payload={
                "user_input": "解释机器学习",
                "expected_output": "机器学习是AI的一个分支",
                "system_prompt": "你是一个专业的AI讲师",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0
        assert result.metadata is not None
        assert result.metadata["tone"] is not None

    def test_text_input_instead_of_user_input_works(self, target, mock_client):
        """使用text字段代替user_input也应正常工作"""
        mock_client.chat.return_value = "预期输出"
        request = EvaluationSchema(
            id="text_003",
            type="text",
            payload={
                "text": "另一个问题",
                "expected_output": "预期输出",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score is not None


class TestTextMatchEvaluatorNegativeCases:
    """负向测试 - 错误输入"""

    @pytest.fixture
    def target(self):
        return TextMatchEvaluator(client=None)

    def test_empty_user_input_returns_error(self, target):
        """空user_input应返回is_valid=False"""
        request = EvaluationSchema(
            id="text_neg_001",
            type="text",
            payload={"user_input": ""},
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert result.error is not None
        assert "不能为空" in result.error

    def test_empty_text_returns_error(self, target):
        """空text字段应返回is_valid=False"""
        request = EvaluationSchema(
            id="text_neg_002",
            type="text",
            payload={"text": ""},
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert result.error is not None

    def test_missing_input_returns_error(self, target):
        """缺少输入字段应返回错误"""
        request = EvaluationSchema(
            id="text_neg_003",
            type="text",
            payload={},
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert result.error is not None


class TestTextMatchEvaluatorDependencyHandling:
    """依赖测试 - 外部依赖Mock"""

    @pytest.fixture
    def mock_client(self):
        """Mock LLM客户端 - 必须设置return_value"""
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        client.chat.return_value = "预期输出"
        return client

    def test_without_llm_client_returns_error(self):
        """无LLM client时应返回is_valid=False, error='LLM client 未配置'"""
        target = TextMatchEvaluator(client=None)
        request = EvaluationSchema(
            id="text_dep_001",
            type="text",
            payload={
                "user_input": "测试问题",
                "expected_output": "预期输出",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert "LLM client" in result.error
        assert "未配置" in result.error

    def test_with_mock_client_calls_chat(self, mock_client):
        """使用Mock客户端时应正常调用chat方法"""
        target = TextMatchEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="text_dep_002",
            type="text",
            payload={
                "user_input": "测试问题",
                "expected_output": "预期输出",
            },
        )
        result = target.evaluate(request)

        mock_client.chat.assert_called_once()
        assert result.is_valid is True

    def test_client_chat_exception_handled(self, mock_client):
        """LLM客户端chat方法抛出异常时应返回错误"""
        mock_client.chat.side_effect = Exception("LLM API Error")
        target = TextMatchEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="text_dep_003",
            type="text",
            payload={
                "user_input": "测试问题",
                "expected_output": "预期输出",
            },
        )
        result = target.safe_evaluate(request)

        assert result.is_valid is False
        assert "LLM API Error" in result.error


class TestTextMatchEvaluatorBoundaryCases:
    """边界测试 - 边界值"""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        client.chat.return_value = "预期输出"
        return client

    def test_none_input_returns_error(self, mock_client):
        """None输入应被正确处理"""
        target = TextMatchEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="text_bound_001",
            type="text",
            payload={"user_input": None},
        )
        result = target.evaluate(request)

        assert result.is_valid is False

    def test_very_long_input_handled(self, mock_client):
        """超长输入应被正确处理"""
        target = TextMatchEvaluator(client=mock_client)
        long_input = "测试" * 1000
        # mock返回与expected_output相同的内容，以获得高分
        mock_client.chat.return_value = long_input
        request = EvaluationSchema(
            id="text_bound_002",
            type="text",
            payload={
                "user_input": long_input,
                "expected_output": long_input,
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0
        mock_client.chat.assert_called_once()

    def test_unicode_chinese_input_handled(self, mock_client):
        """中文Unicode输入应被正确处理"""
        target = TextMatchEvaluator(client=mock_client)
        # mock返回与expected_output相同的内容，以获得高分
        mock_client.chat.return_value = "你好，世界！"
        request = EvaluationSchema(
            id="text_bound_003",
            type="text",
            payload={
                "user_input": "你好，世界！",
                "expected_output": "你好，世界！",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0

    def test_empty_expected_output_with_client(self, mock_client):
        """expected_output为空时应有合理的默认行为"""
        mock_client.chat.return_value = "回答内容"
        target = TextMatchEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="text_bound_004",
            type="text",
            payload={
                "user_input": "测试问题",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score is not None


class TestTextMatchEvaluatorScoringLogic:
    """评分逻辑测试"""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        return client

    def test_identical_output_gets_full_score(self, mock_client):
        """完全相同的输出应得到满分"""
        mock_client.chat.return_value = "完全相同的内容"
        target = TextMatchEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="text_score_001",
            type="text",
            payload={
                "user_input": "问题",
                "expected_output": "完全相同的内容",
            },
        )
        result = target.evaluate(request)

        assert result.score == 1.0
        assert result.is_valid is True

    def test_completely_different_output_gets_low_score(self, mock_client):
        """完全不同的输出应得到低分"""
        mock_client.chat.return_value = "xyz123abc"
        target = TextMatchEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="text_score_002",
            type="text",
            payload={
                "user_input": "问题",
                "expected_output": "完全不同的答案内容xyz123",
            },
        )
        result = target.evaluate(request)

        assert result.score < 1.0
        assert result.score >= 0.0
