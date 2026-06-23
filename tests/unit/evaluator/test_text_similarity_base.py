"""
TextSimilarityBasedEvaluator 专项测试
测试目标：验证基于文本相似度评估的抽象基类及其子类(QAEvaluator/SemanticEvaluator/SummaryEvaluator)的核心能力
关键发现：TextSimilarityBasedEvaluator定义了统一的评估流程(_do_evaluate)，子类只需实现build_prompt()；文件存在重复注册qa/semantic/summary的问题
"""

from unittest.mock import MagicMock

import pytest

from src.domain.evaluators.text_similarity_base import (
    TextSimilarityBasedEvaluator,
)
from src.schemas.evaluation import EvaluationSchema


class TestTextSimilarityBasedEvaluatorBase:
    """基类测试"""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.chat.return_value = "LLM输出内容"
        return client

    def test_do_evaluate_with_client(self, mock_client):
        """有LLM客户端时应调用_client"""
        request = EvaluationSchema(
            id="test-1",
            type="qa",
            payload={"expected_output": "预期答案"},
        )

        class TestEvaluator(TextSimilarityBasedEvaluator):
            def build_prompt(self, user_input, request):
                return f"Prompt: {user_input}"

            def evaluate(self, request):
                return self._do_evaluate(request)

        evaluator = TestEvaluator(client=mock_client)
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.text == "LLM输出内容"
        mock_client.chat.assert_called_once()

    def test_do_evaluate_without_client(self):
        """无LLM客户端时应降级返回prompt"""
        request = EvaluationSchema(
            id="test-2",
            type="qa",
            payload={"expected_output": "预期答案"},
        )

        class TestEvaluator(TextSimilarityBasedEvaluator):
            def build_prompt(self, user_input, request):
                return "测试Prompt"

            def evaluate(self, request):
                return self._do_evaluate(request)

        evaluator = TestEvaluator(client=None)
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.text == "测试Prompt"

    def test_calculate_score_with_expected_output(self):
        """有expected_output时应计算相似度分数"""

        class TestEvaluator(TextSimilarityBasedEvaluator):
            def build_prompt(self, user_input, request):
                return "测试Prompt"

            def evaluate(self, request):
                return self._do_evaluate(request)

        evaluator = TestEvaluator()
        score = evaluator._calculate_score("Hello world", "Hello world")
        assert isinstance(score, float)
        assert 0 <= score <= 1.0

    def test_calculate_score_without_expected_output(self):
        """无expected_output时应返回1.0"""

        class TestEvaluator(TextSimilarityBasedEvaluator):
            def build_prompt(self, user_input, request):
                return "测试Prompt"

            def evaluate(self, request):
                return self._do_evaluate(request)

        evaluator = TestEvaluator()
        score = evaluator._calculate_score("Hello world", None)
        assert score == 1.0

    def test_call_llm_exception_returns_prompt(self):
        """LLM调用异常时应降级返回prompt"""
        mock_client = MagicMock()
        mock_client.chat.side_effect = Exception("LLM错误")

        class TestEvaluator(TextSimilarityBasedEvaluator):
            def build_prompt(self, user_input, request):
                return "测试Prompt"

            def evaluate(self, request):
                return self._do_evaluate(request)

        evaluator = TestEvaluator(client=mock_client)
        result = evaluator._call_llm("测试Prompt")
        assert result == "测试Prompt"

    def test_get_evaluator_name_default(self):
        """默认评估器名称应为text_similarity"""

        class TestEvaluator(TextSimilarityBasedEvaluator):
            def build_prompt(self, user_input, request):
                return "测试Prompt"

            def evaluate(self, request):
                return self._do_evaluate(request)

        evaluator = TestEvaluator()
        assert evaluator.get_evaluator_name() == "text_similarity"


class TestTextSimilarityBaseIntegration:
    """集成测试"""

    def test_text_similarity_base_registered(self):
        """TextSimilarityBasedEvaluator应已注册到工厂"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory

        assert "text_similarity_base" in EvaluatorFactory.list_evaluators()

    def test_three_evaluator_names_registered(self):
        """三个评估器名称应已注册到工厂"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory

        evaluators = EvaluatorFactory.list_evaluators()
        assert "qa" in evaluators
        assert "semantic" in evaluators
        assert "summary" in evaluators
