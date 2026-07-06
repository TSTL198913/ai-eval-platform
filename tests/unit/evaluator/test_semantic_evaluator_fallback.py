"""
SemanticEvaluator 2026年工业级标准降级策略测试
测试目标：验证LLM调用异常时降级策略是否生效，返回PARTIAL状态
标准依据：2026年AI评测工业级标准 - 降级透明度原则
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.semantic import SemanticEvaluator
from src.schemas.evaluation import EvaluationSchema, EvaluatorStatus


class MockFailingLLMClient:
    """模拟LLM客户端调用失败"""
    def chat(self, prompt: str) -> str:
        raise RuntimeError("LLM服务不可用")


class MockInvalidResponseLLMClient:
    """模拟LLM返回无法解析的响应"""
    def chat(self, prompt: str) -> str:
        return "无法解析的响应内容"


class TestSemanticEvaluatorFallbackPolicy:
    """降级策略测试"""

    def test_llm_failure_should_trigger_fallback(self):
        """
        标准：LLM调用失败时必须触发降级策略
        场景：LLM服务不可用
        """
        evaluator = SemanticEvaluator(client=MockFailingLLMClient())
        
        request = EvaluationSchema(
            id="semantic_fallback_001",
            type="semantic",
            payload={
                "user_input": "什么是机器学习？",
                "actual_output": "机器学习是一种人工智能技术",
                "expected_output": "机器学习是人工智能的一个分支",
            },
        )

        result = evaluator.safe_evaluate(request)

        assert result.evaluation_status == EvaluatorStatus.PARTIAL, \
            f"LLM失败时应返回PARTIAL状态，实际返回: {result.evaluation_status}"
        assert result.score is not None, "降级评估应返回score"
        assert 0.0 <= result.score <= 1.0, f"score应在[0,1]区间，实际: {result.score}"

    def test_llm_invalid_response_should_trigger_fallback(self):
        """
        标准：LLM返回无法解析的响应时必须触发降级策略
        场景：LLM返回非数字响应
        """
        evaluator = SemanticEvaluator(client=MockInvalidResponseLLMClient())
        
        request = EvaluationSchema(
            id="semantic_fallback_002",
            type="semantic",
            payload={
                "user_input": "什么是机器学习？",
                "actual_output": "机器学习是一种人工智能技术",
                "expected_output": "机器学习是人工智能的一个分支",
            },
        )

        result = evaluator.safe_evaluate(request)

        assert result.evaluation_status == EvaluatorStatus.PARTIAL, \
            f"LLM响应无法解析时应返回PARTIAL状态，实际返回: {result.evaluation_status}"
        assert result.score is not None, "降级评估应返回score"

    def test_fallback_should_have_confidence_level(self):
        """
        标准：降级评估必须包含confidence_level
        场景：LLM服务不可用
        """
        evaluator = SemanticEvaluator(client=MockFailingLLMClient())
        
        request = EvaluationSchema(
            id="semantic_fallback_003",
            type="semantic",
            payload={
                "user_input": "什么是机器学习？",
                "actual_output": "机器学习是一种人工智能技术",
                "expected_output": "机器学习是人工智能的一个分支",
            },
        )

        result = evaluator.safe_evaluate(request)

        assert hasattr(result, "confidence_level"), "降级评估必须包含confidence_level"
        assert result.confidence_level is not None, "confidence_level不能为空"

    def test_fallback_should_have_confidence_components(self):
        """
        标准：降级评估必须包含confidence_auto_computed和confidence_components
        场景：LLM服务不可用
        """
        evaluator = SemanticEvaluator(client=MockFailingLLMClient())
        
        request = EvaluationSchema(
            id="semantic_fallback_004",
            type="semantic",
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
        场景：LLM服务不可用（embedding服务可用时使用embedding，否则使用rule_based）
        """
        evaluator = SemanticEvaluator(client=MockFailingLLMClient())
        
        request = EvaluationSchema(
            id="semantic_fallback_005",
            type="semantic",
            payload={
                "user_input": "什么是机器学习？",
                "actual_output": "机器学习是一种人工智能技术",
                "expected_output": "机器学习是人工智能的一个分支",
            },
        )

        result = evaluator.safe_evaluate(request)

        assert "evaluation_method" in (result.data or {}), "降级评估必须包含evaluation_method"
        eval_method = result.data.get("evaluation_method")
        assert eval_method in ["embedding", "rule_based"], \
            f"降级评估方法应为embedding或rule_based，实际: {eval_method}"

    def test_skip_reasons_should_be_recorded(self):
        """
        标准：降级评估必须记录跳过原因
        场景：LLM服务不可用
        """
        evaluator = SemanticEvaluator(client=MockFailingLLMClient())
        
        request = EvaluationSchema(
            id="semantic_fallback_006",
            type="semantic",
            payload={
                "user_input": "什么是机器学习？",
                "actual_output": "机器学习是一种人工智能技术",
                "expected_output": "机器学习是人工智能的一个分支",
            },
        )

        result = evaluator.safe_evaluate(request)

        assert "dimensions_skipped" in (result.data or {}), "降级评估必须包含dimensions_skipped"
        assert "llm_semantic" in result.data.get("dimensions_skipped", []), \
            "llm_semantic维度应被标记为跳过"
        assert "skip_reasons" in (result.data or {}), "降级评估必须包含skip_reasons"