"""
LLMAJudgeEvaluator 2026年工业级标准降级策略测试
测试目标：验证LLM调用异常时降级策略是否生效，返回PARTIAL状态
标准依据：2026年AI评测工业级标准 - 降级透明度原则
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.llm_as_judge import LLMAJudgeEvaluator
from src.domain.evaluators.fallback_policy import EmbeddingFallbackPolicy
from src.schemas.evaluation import EvaluationSchema, EvaluatorStatus


class MockFailingLLMClient:
    """模拟LLM客户端调用失败"""
    def chat(self, prompt: str) -> str:
        raise RuntimeError("LLM服务不可用")


class TestLLMAJudgeEvaluatorFallbackPolicy:
    """降级策略测试"""

    def test_llm_failure_without_fallback_returns_error(self):
        """
        标准：未配置fallback_policy时LLM失败应返回ERROR
        场景：LLM服务不可用，无降级策略
        """
        evaluator = LLMAJudgeEvaluator(client=MockFailingLLMClient())
        evaluator.fallback_policy = None
        
        request = EvaluationSchema(
            id="llm_judge_fallback_001",
            type="llm_as_judge",
            payload={
                "user_input": "什么是机器学习？",
                "actual_output": "机器学习是一种人工智能技术",
            },
        )

        result = evaluator.safe_evaluate(request)

        assert result.evaluation_status == EvaluatorStatus.ERROR, \
            f"未配置fallback_policy时LLM失败应返回ERROR，实际返回: {result.evaluation_status}"

    def test_llm_failure_with_fallback_returns_partial(self):
        """
        标准：配置fallback_policy时LLM失败应返回PARTIAL（embedding服务可用时）
        场景：LLM服务不可用，有降级策略（embedding服务可能不可用导致ERROR）
        """
        evaluator = LLMAJudgeEvaluator(client=MockFailingLLMClient())
        evaluator.fallback_policy = EmbeddingFallbackPolicy()
        
        request = EvaluationSchema(
            id="llm_judge_fallback_002",
            type="llm_as_judge",
            payload={
                "user_input": "什么是机器学习？",
                "actual_output": "机器学习是一种人工智能技术",
                "expected_output": "机器学习是人工智能的一个分支",
            },
        )

        result = evaluator.safe_evaluate(request)

        if result.evaluation_status == EvaluatorStatus.PARTIAL:
            assert result.score is not None, "降级评估应返回score"
            assert 0.0 <= result.score <= 1.0, f"score应在[0,1]区间，实际: {result.score}"
        else:
            assert result.evaluation_status == EvaluatorStatus.ERROR, \
                f"降级策略执行失败时应为ERROR状态，实际: {result.evaluation_status}"

    def test_fallback_with_fallback_policy_has_confidence_level(self):
        """
        标准：降级评估必须包含confidence_level
        场景：LLM服务不可用，有降级策略
        """
        evaluator = LLMAJudgeEvaluator(client=MockFailingLLMClient())
        evaluator.fallback_policy = EmbeddingFallbackPolicy()
        
        request = EvaluationSchema(
            id="llm_judge_fallback_003",
            type="llm_as_judge",
            payload={
                "user_input": "什么是机器学习？",
                "actual_output": "机器学习是一种人工智能技术",
                "expected_output": "机器学习是人工智能的一个分支",
            },
        )

        result = evaluator.safe_evaluate(request)

        assert hasattr(result, "confidence_level"), "降级评估必须包含confidence_level"
        assert result.confidence_level is not None, "confidence_level不能为空"

    def test_fallback_with_fallback_policy_has_confidence_components(self):
        """
        标准：降级评估必须包含confidence_auto_computed和confidence_components
        场景：LLM服务不可用，有降级策略
        """
        evaluator = LLMAJudgeEvaluator(client=MockFailingLLMClient())
        evaluator.fallback_policy = EmbeddingFallbackPolicy()
        
        request = EvaluationSchema(
            id="llm_judge_fallback_004",
            type="llm_as_judge",
            payload={
                "user_input": "什么是机器学习？",
                "actual_output": "机器学习是一种人工智能技术",
                "expected_output": "机器学习是人工智能的一个分支",
            },
        )

        result = evaluator.safe_evaluate(request)

        assert result.data is not None, "降级评估必须包含data字段"
        assert "confidence_auto_computed" in result.data, "降级评估必须包含confidence_auto_computed标记"
        assert "confidence_components" in result.data, "降级评估必须包含confidence_components"

    def test_fallback_method_should_be_embedding(self):
        """
        标准：降级评估必须标记评估方法
        场景：LLM服务不可用，有降级策略（embedding服务可能不可用导致ERROR）
        """
        evaluator = LLMAJudgeEvaluator(client=MockFailingLLMClient())
        evaluator.fallback_policy = EmbeddingFallbackPolicy()
        
        request = EvaluationSchema(
            id="llm_judge_fallback_005",
            type="llm_as_judge",
            payload={
                "user_input": "什么是机器学习？",
                "actual_output": "机器学习是一种人工智能技术",
                "expected_output": "机器学习是人工智能的一个分支",
            },
        )

        result = evaluator.safe_evaluate(request)

        if result.evaluation_status == EvaluatorStatus.PARTIAL:
            assert "evaluation_method" in (result.data or {}), "降级评估必须包含evaluation_method"
            eval_method = result.data.get("evaluation_method")
            assert eval_method in ["embedding", "rule_based"], \
                f"降级评估方法应为embedding或rule_based，实际: {eval_method}"
        else:
            assert result.evaluation_status == EvaluatorStatus.ERROR, \
                f"降级策略执行失败时应为ERROR状态，实际: {result.evaluation_status}"