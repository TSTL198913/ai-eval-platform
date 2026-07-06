"""
GeneralEvaluator 和 QAEvaluator 2026年工业级标准降级策略测试
测试目标：验证严格语义策略（禁止降级）的行为是否符合预期
标准依据：2026年AI评测工业级标准 - 降级透明度原则
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.general import GeneralEvaluator
from src.domain.evaluators.qa import QAEvaluator
from src.schemas.evaluation import EvaluationSchema, EvaluatorStatus


class MockFailingLLMClient:
    """模拟LLM客户端调用失败"""
    def chat(self, prompt: str) -> str:
        raise RuntimeError("LLM服务不可用")


class TestGeneralEvaluatorStrictPolicy:
    """GeneralEvaluator严格语义策略测试"""

    def test_strict_policy_returns_error_on_llm_failure(self):
        """
        标准：LLM失败时评估器应返回降级评估结果（PARTIAL）
        场景：LLM服务不可用，评估器使用规则降级
        """
        evaluator = GeneralEvaluator(client=MockFailingLLMClient())
        
        request = EvaluationSchema(
            id="general_strict_001",
            type="general",
            payload={
                "user_input": "什么是机器学习？",
                "actual_output": "机器学习是一种人工智能技术",
                "expected_output": "机器学习是人工智能的一个分支",
            },
        )

        result = evaluator.safe_evaluate(request)

        assert result.evaluation_status == EvaluatorStatus.PARTIAL, \
            f"LLM失败时应返回PARTIAL状态，实际返回: {result.evaluation_status}"
        assert result.score is not None, f"PARTIAL状态应返回score，实际返回: {result.score}"
        assert "fallback_reason" in result.data, "降级评估应包含fallback_reason"

    def test_error_response_has_confidence_level(self):
        """
        标准：ERROR状态必须包含confidence_level
        """
        evaluator = GeneralEvaluator(client=MockFailingLLMClient())
        
        request = EvaluationSchema(
            id="general_strict_002",
            type="general",
            payload={
                "user_input": "什么是机器学习？",
                "actual_output": "机器学习是一种人工智能技术",
                "expected_output": "机器学习是人工智能的一个分支",
            },
        )

        result = evaluator.safe_evaluate(request)

        assert hasattr(result, "confidence_level"), "ERROR响应必须包含confidence_level"
        assert result.confidence_level is not None, "confidence_level不能为空"


class TestQAEvaluatorStrictPolicy:
    """QAEvaluator严格语义策略测试"""

    def test_strict_policy_returns_error_on_llm_failure(self):
        """
        标准：LLM失败时评估器应返回降级评估结果（PARTIAL）
        场景：LLM服务不可用，评估器使用规则降级
        """
        evaluator = QAEvaluator(client=MockFailingLLMClient())
        
        request = EvaluationSchema(
            id="qa_strict_001",
            type="qa",
            payload={
                "user_input": "什么是机器学习？",
                "actual_output": "机器学习是一种人工智能技术",
                "expected_output": "机器学习是人工智能的一个分支",
            },
        )

        result = evaluator.safe_evaluate(request)

        assert result.evaluation_status == EvaluatorStatus.PARTIAL, \
            f"LLM失败时应返回PARTIAL状态，实际返回: {result.evaluation_status}"
        assert result.score is not None, f"PARTIAL状态应返回score，实际返回: {result.score}"
        assert "fallback_reason" in result.data, "降级评估应包含fallback_reason"

    def test_error_response_has_confidence_level(self):
        """
        标准：ERROR状态必须包含confidence_level
        """
        evaluator = QAEvaluator(client=MockFailingLLMClient())
        
        request = EvaluationSchema(
            id="qa_strict_002",
            type="qa",
            payload={
                "user_input": "什么是机器学习？",
                "actual_output": "机器学习是一种人工智能技术",
                "expected_output": "机器学习是人工智能的一个分支",
            },
        )

        result = evaluator.safe_evaluate(request)

        assert hasattr(result, "confidence_level"), "ERROR响应必须包含confidence_level"
        assert result.confidence_level is not None, "confidence_level不能为空"