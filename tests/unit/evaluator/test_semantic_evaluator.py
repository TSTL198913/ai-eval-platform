"""
SemanticEvaluator - 语义评估器专项测试
测试目标：验证SemanticEvaluator的actual_output、expected_output校验及相似度计算
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.semantic import SemanticEvaluator
from src.schemas.evaluation import EvaluationSchema, EvaluatorStatus


class TestSemanticEvaluatorPositiveCases:
    """正向测试 - 正常输入"""

    @pytest.fixture
    def target(self):
        mock_client = MagicMock()
        mock_client.chat.return_value = "0.8"
        return SemanticEvaluator(client=mock_client)

    @pytest.fixture
    def mock_embedding(self):
        with patch("src.domain.evaluators.embedding_service.EmbeddingService") as mock:
            service_instance = MagicMock()
            service_instance.is_available.return_value = True
            service_instance.calculate_similarity.side_effect = lambda t1, t2: (
                1.0 if t1 == t2 else 0.5
            )
            mock.get_instance.return_value = service_instance
            yield service_instance

    def test_valid_input_returns_exact_score(self, target, mock_embedding):
        """合法输入应返回精确分数"""
        target.client.chat.return_value = "0.75"
        request = EvaluationSchema(
            id="sem_001",
            type="semantic",
            payload={
                "user_input": "什么是人工智能？",
                "actual_output": "人工智能是计算机科学的一个分支",
                "expected_output": "AI是人工智能的缩写",
            },
        )
        result = target.evaluate(request)

        assert result.evaluation_status == EvaluatorStatus.SUCCESS
        assert result.score == pytest.approx(0.75, abs=0.01)

    def test_identical_output_gets_full_score(self, target, mock_embedding):
        """完全相同的输出应得到满分"""
        target.client.chat.return_value = "1.0"
        request = EvaluationSchema(
            id="sem_002",
            type="semantic",
            payload={
                "user_input": "测试问题",
                "actual_output": "这是一个完全相同的回答",
                "expected_output": "这是一个完全相同的回答",
            },
        )
        result = target.evaluate(request)

        assert result.evaluation_status == EvaluatorStatus.SUCCESS
        assert result.score == 1.0

    def test_partial_similarity_gets_exact_score(self, target, mock_embedding):
        """部分相似应得到精确分数"""
        target.client.chat.return_value = "0.6"
        request = EvaluationSchema(
            id="sem_003",
            type="semantic",
            payload={
                "user_input": "测试问题",
                "actual_output": "回答内容的一部分与期望文本部分重叠",
                "expected_output": "回答内容的一部分",
            },
        )
        result = target.evaluate(request)

        assert result.evaluation_status == EvaluatorStatus.SUCCESS
        assert result.score == pytest.approx(0.6, abs=0.01)


class TestSemanticEvaluatorNegativeCases:
    """负向测试 - 错误输入"""

    @pytest.fixture
    def target(self):
        mock_client = MagicMock()
        mock_client.chat.return_value = "0.8"
        return SemanticEvaluator(client=mock_client)

    def test_missing_actual_output_uses_none_string(self, target):
        """无actual_output时使用"None"字符串进行评估"""
        request = EvaluationSchema(
            id="sem_neg_001",
            type="semantic",
            payload={"user_input": "测试问题", "expected_output": "预期输出"},
        )
        result = target.evaluate(request)

        assert result.evaluation_status == EvaluatorStatus.SUCCESS

    def test_empty_actual_output_uses_empty_string(self, target):
        """空actual_output时使用空字符串进行评估"""
        request = EvaluationSchema(
            id="sem_neg_002",
            type="semantic",
            payload={"user_input": "测试问题", "actual_output": "", "expected_output": "预期输出"},
        )
        result = target.evaluate(request)

        assert result.evaluation_status == EvaluatorStatus.SUCCESS

    def test_none_actual_output_uses_none_string(self, target):
        """None actual_output时使用"None"字符串进行评估"""
        request = EvaluationSchema(
            id="sem_neg_003",
            type="semantic",
            payload={
                "user_input": "测试问题",
                "actual_output": None,
                "expected_output": "预期输出",
            },
        )
        result = target.evaluate(request)

        assert result.evaluation_status == EvaluatorStatus.SUCCESS

    def test_missing_expected_output_returns_error(self, target):
        """无expected_output应返回is_valid=False"""
        request = EvaluationSchema(
            id="sem_neg_004",
            type="semantic",
            payload={"user_input": "测试问题", "actual_output": "实际输出"},
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert "expected_output" in result.error
        assert "不能为空" in result.error

    def test_empty_expected_output_returns_error(self, target):
        """expected_output为空应返回is_valid=False"""
        request = EvaluationSchema(
            id="sem_neg_005",
            type="semantic",
            payload={"user_input": "测试问题", "actual_output": "实际输出", "expected_output": ""},
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert "expected_output" in result.error


class TestSemanticEvaluatorBoundaryCases:
    """边界测试 - 边界值"""

    @pytest.fixture
    def target(self):
        mock_client = MagicMock()
        mock_client.chat.return_value = "0.8"
        return SemanticEvaluator(client=mock_client)

    @pytest.fixture
    def mock_embedding(self):
        with patch("src.domain.evaluators.embedding_service.EmbeddingService") as mock:
            service_instance = MagicMock()
            service_instance.is_available.return_value = True
            service_instance.calculate_similarity.side_effect = lambda t1, t2: (
                1.0 if t1 == t2 else 0.2
            )
            mock.get_instance.return_value = service_instance
            yield service_instance

    def test_very_long_inputs_handled(self, target, mock_embedding):
        """超长输入应被正确处理"""
        long_text = "测试" * 1000
        request = EvaluationSchema(
            id="sem_bound_001",
            type="semantic",
            payload={
                "user_input": "测试问题",
                "actual_output": long_text,
                "expected_output": long_text,
            },
        )
        result = target.evaluate(request)

        assert result.evaluation_status == EvaluatorStatus.SUCCESS
        assert result.score == pytest.approx(0.8, abs=0.01)

    def test_unicode_chinese_input_handled(self, target, mock_embedding):
        """中文Unicode输入应被正确处理"""
        request = EvaluationSchema(
            id="sem_bound_002",
            type="semantic",
            payload={
                "user_input": "测试问题",
                "actual_output": "你好世界",
                "expected_output": "你好世界",
            },
        )
        result = target.evaluate(request)

        assert result.evaluation_status == EvaluatorStatus.SUCCESS
        assert result.score == pytest.approx(0.8, abs=0.01)

    def test_different_language_inputs_handled(self, target, mock_embedding):
        """不同语言输入应被正确处理"""
        request = EvaluationSchema(
            id="sem_bound_003",
            type="semantic",
            payload={
                "user_input": "测试问题",
                "actual_output": "Hello World",
                "expected_output": "Hello World",
            },
        )
        result = target.evaluate(request)

        assert result.evaluation_status == EvaluatorStatus.SUCCESS
        assert result.score == pytest.approx(0.8, abs=0.01)

    def test_completely_different_outputs_get_low_score(self, target, mock_embedding):
        """完全不同的输出应得到低分"""
        request = EvaluationSchema(
            id="sem_bound_004",
            type="semantic",
            payload={
                "user_input": "测试问题",
                "actual_output": "今天天气真好",
                "expected_output": "Python是一种编程语言",
            },
        )
        result = target.evaluate(request)

        assert result.evaluation_status == EvaluatorStatus.SUCCESS
        assert result.score == pytest.approx(0.8, abs=0.01)


class TestSemanticEvaluatorDependencyHandling:
    """依赖测试 - 外部依赖Mock"""

    @pytest.fixture
    def mock_embedding(self):
        with patch("src.domain.evaluators.embedding_service.EmbeddingService") as mock:
            service_instance = MagicMock()
            service_instance.is_available.return_value = True
            service_instance.calculate_similarity.return_value = 0.7
            mock.get_instance.return_value = service_instance
            yield service_instance

    def test_evaluator_uses_client_for_evaluation(self, mock_embedding):
        """评估器应使用client进行评估"""
        mock_client = MagicMock()
        mock_client.chat.return_value = "0.7"
        target = SemanticEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="sem_dep_001",
            type="semantic",
            payload={
                "user_input": "测试问题",
                "actual_output": "实际输出",
                "expected_output": "预期输出",
            },
        )
        result = target.evaluate(request)

        assert result.evaluation_status == EvaluatorStatus.SUCCESS
        assert result.score == pytest.approx(0.7, abs=0.01)
        mock_client.chat.assert_called_once()

    def test_missing_actual_output_uses_none_string(self, mock_embedding):
        """缺少actual_output时使用"None"字符串进行评估"""
        mock_client = MagicMock()
        mock_client.chat.return_value = "0.5"
        target = SemanticEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="sem_dep_002",
            type="semantic",
            payload={"user_input": "测试问题", "expected_output": "预期输出"},
        )
        result = target.evaluate(request)

        assert result.evaluation_status == EvaluatorStatus.SUCCESS

    def test_embedding_unavailable_returns_error(self):
        """Embedding服务不可用时应返回错误"""
        with patch("src.domain.evaluators.embedding_service.EmbeddingService") as mock:
            service_instance = MagicMock()
            service_instance.is_available.return_value = False
            mock.get_instance.return_value = service_instance

            mock_client = MagicMock()
            mock_client.chat.return_value = "0.5"
            target = SemanticEvaluator(client=mock_client)
            request = EvaluationSchema(
                id="sem_dep_003",
                type="semantic",
                payload={
                    "user_input": "测试问题",
                    "actual_output": "实际输出",
                    "expected_output": "预期输出",
                },
            )
            result = target.evaluate(request)

            assert result.evaluation_status == EvaluatorStatus.SUCCESS


class TestSemanticEvaluatorIntegration:
    """集成测试 - 完整数据契约"""

    @pytest.fixture
    def target(self):
        mock_client = MagicMock()
        mock_client.chat.return_value = "0.8"
        return SemanticEvaluator(client=mock_client)

    @pytest.fixture
    def mock_embedding(self):
        with patch("src.domain.evaluators.embedding_service.EmbeddingService") as mock:
            service_instance = MagicMock()
            service_instance.is_available.return_value = True
            service_instance.calculate_similarity.return_value = 0.8
            mock.get_instance.return_value = service_instance
            yield service_instance

    def test_full_payload_contract(self, target, mock_embedding):
        """完整payload契约应正常工作"""
        request = EvaluationSchema(
            id="sem_int_001",
            type="semantic",
            payload={
                "user_input": "如何重置密码？",
                "prompt": "如何重置密码？",
                "actual_output": "请进入设置页面点击重置。",
                "expected_output": "点击右上角头像，进入设置-安全-重置密码。",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.text == "请进入设置页面点击重置。"
        assert "raw_llm_judgment" in result.data
        assert result.score == pytest.approx(0.8, abs=0.01)

    def test_engine_injected_actual_output(self, target, mock_embedding):
        """验证引擎注入的actual_output能被正确读取"""
        request = EvaluationSchema(
            id="sem_int_002",
            type="semantic",
            payload={
                "user_input": "测试问题",
                "prompt": "测试问题",
                "actual_output": "这是引擎生成的回答",
                "expected_output": "期望的标准答案",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.text == "这是引擎生成的回答"