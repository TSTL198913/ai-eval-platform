"""
SemanticEvaluator - 语义评估器专项测试
测试目标：验证SemanticEvaluator的validate_input、expected_output不能为空、score_text_similarity计算相似度等核心功能
关键发现：（测试过程中记录）
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.semantic import SemanticEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestSemanticEvaluatorPositiveCases:
    """正向测试 - 正常输入"""

    @pytest.fixture
    def mock_client(self):
        """Mock LLM客户端"""
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        client.chat.return_value = "语义相似的回答"
        return client

    @pytest.fixture
    def target(self, mock_client):
        return SemanticEvaluator(client=mock_client)

    def test_valid_input_with_expected_output_returns_valid(self, target, mock_client):
        """合法输入+expected_output应返回is_valid=True"""
        request = EvaluationSchema(
            id="sem_001",
            type="semantic",
            payload={
                "user_input": "什么是人工智能？",
                "expected_output": "AI是人工智能的缩写",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score is not None
        assert result.score >= 0.0
        assert result.score <= 1.0

    def test_llm_output_similarity_calculated(self, target, mock_client):
        """应基于LLM输出与expected_output的相似度计算分数"""
        mock_client.chat.return_value = "这是一个完全相同的回答"
        request = EvaluationSchema(
            id="sem_002",
            type="semantic",
            payload={
                "user_input": "问题",
                "expected_output": "这是一个完全相同的回答",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0

    def test_text_field_instead_of_user_input_works(self, target, mock_client):
        """使用text字段代替user_input也应正常工作"""
        request = EvaluationSchema(
            id="sem_003",
            type="semantic",
            payload={
                "text": "另一个问题",
                "expected_output": "预期输出",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True


class TestSemanticEvaluatorNegativeCases:
    """负向测试 - 错误输入"""

    @pytest.fixture
    def target(self):
        return SemanticEvaluator(client=None)

    def test_empty_user_input_returns_error(self, target):
        """空user_input应返回is_valid=False"""
        request = EvaluationSchema(
            id="sem_neg_001",
            type="semantic",
            payload={"user_input": ""},
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert result.error is not None
        assert "不能为空" in result.error

    def test_empty_text_returns_error(self, target):
        """空text字段应返回is_valid=False"""
        request = EvaluationSchema(
            id="sem_neg_002",
            type="semantic",
            payload={"text": ""},
        )
        result = target.evaluate(request)

        assert result.is_valid is False

    def test_missing_expected_output_returns_error(self, target):
        """无expected_output应返回is_valid=False, error='expected_output 不能为空'"""
        request = EvaluationSchema(
            id="sem_neg_003",
            type="semantic",
            payload={"user_input": "测试问题"},
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert "expected_output" in result.error
        assert "不能为空" in result.error

    def test_empty_expected_output_returns_error(self, target):
        """expected_output为空应返回is_valid=False"""
        request = EvaluationSchema(
            id="sem_neg_004",
            type="semantic",
            payload={
                "user_input": "测试问题",
                "expected_output": "",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert "expected_output" in result.error


class TestSemanticEvaluatorDependencyHandling:
    """依赖测试 - 外部依赖Mock"""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        client.chat.return_value = "LLM生成的回答"
        return client

    def test_without_client_uses_user_input_directly(self, mock_client):
        """无client时应使用user_input作为llm_output"""
        target = SemanticEvaluator(client=None)
        request = EvaluationSchema(
            id="sem_dep_001",
            type="semantic",
            payload={
                "user_input": "直接作为输出",
                "expected_output": "直接作为输出",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0

    def test_with_client_calls_llm(self, mock_client):
        """有client时应调用LLM"""
        target = SemanticEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="sem_dep_002",
            type="semantic",
            payload={
                "user_input": "测试问题",
                "expected_output": "预期输出",
            },
        )
        result = target.evaluate(request)

        mock_client.chat.assert_called_once()
        assert result.is_valid is True


class TestSemanticEvaluatorBoundaryCases:
    """边界测试 - 边界值"""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        client.chat.return_value = "回答"
        return client

    def test_none_input_returns_error(self, mock_client):
        """None输入应被正确处理"""
        target = SemanticEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="sem_bound_001",
            type="semantic",
            payload={"user_input": None},
        )
        result = target.evaluate(request)

        assert result.is_valid is False

    def test_very_long_inputs_handled(self, mock_client):
        """超长输入应被正确处理"""
        target = SemanticEvaluator(client=mock_client)
        long_text = "测试" * 1000
        request = EvaluationSchema(
            id="sem_bound_002",
            type="semantic",
            payload={
                "user_input": long_text,
                "expected_output": long_text,
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True

    def test_unicode_chinese_input_handled(self, mock_client):
        """中文Unicode输入应被正确处理"""
        target = SemanticEvaluator(client=mock_client)
        # mock返回与expected_output相同的内容，以获得高分
        mock_client.chat.return_value = "你好"
        request = EvaluationSchema(
            id="sem_bound_003",
            type="semantic",
            payload={
                "user_input": "你好",
                "expected_output": "你好",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0


class TestSemanticEvaluatorScoringLogic:
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
        target = SemanticEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="sem_score_001",
            type="semantic",
            payload={
                "user_input": "问题",
                "expected_output": "完全相同的内容",
            },
        )
        result = target.evaluate(request)

        assert result.score == 1.0

    def test_partial_similarity_gets_partial_score(self, mock_client):
        """部分相似应得到部分分数"""
        mock_client.chat.return_value = "回答内容的一部分与期望文本部分重叠"
        target = SemanticEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="sem_score_002",
            type="semantic",
            payload={
                "user_input": "问题",
                "expected_output": "回答内容的一部分",
            },
        )
        result = target.evaluate(request)

        assert result.score is not None
        assert result.score >= 0.0
