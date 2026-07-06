"""
BaseEvaluator evaluate_async 2026年工业级标准合规性测试
测试目标：验证evaluate_async必须调用_auto_compute_confidence
标准依据：2026年AI评测工业级标准 - 置信度完整性原则
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.security import SecurityEvaluator
from src.domain.evaluators.code import CodeEvaluator
from src.schemas.evaluation import EvaluationSchema, EvaluatorStatus
from unittest.mock import MagicMock


class TestBaseEvaluatorAsyncConfidence:
    """2026年工业级标准合规性测试 - evaluate_async置信度计算"""

    @pytest.mark.asyncio
    async def test_evaluate_async_must_compute_confidence(self):
        """
        标准：evaluate_async必须调用_auto_compute_confidence
        场景：异步评估结果必须包含置信度自动计算标记或已有明确置信度
        """
        evaluator = SecurityEvaluator(client=None)

        request = EvaluationSchema(
            id="async_conf_001",
            type="security",
            payload={"text": "安全的文本"},
        )

        result = await evaluator.evaluate_async(request)

        assert result.confidence is not None, "异步评估结果必须有置信度"
        assert result.confidence > 0, "异步评估结果置信度必须>0"
        
        has_auto_computed = "confidence_auto_computed" in result.data
        has_explicit_confidence = result.confidence is not None and result.confidence > 0
        assert has_auto_computed or has_explicit_confidence, "evaluate_async必须设置置信度"

    @pytest.mark.asyncio
    async def test_evaluate_async_must_add_confidence_components(self):
        """
        标准：evaluate_async必须添加置信度信息
        场景：异步评估结果必须包含置信度计算（显式设置或自动计算）
        使用ERROR状态的评估，此时不会有显式置信度设置
        """
        evaluator = CodeEvaluator(client=None)

        request = EvaluationSchema(
            id="async_conf_001b",
            type="code",
            payload={"code": "def hello()\n    return 'Hello'"},
        )

        result = await evaluator.evaluate_async(request)

        assert result.score == 0.0, f"语法错误应返回score=0.0，实际: {result.score}"
        assert "confidence_auto_computed" in result.data, "evaluate_async必须调用_auto_compute_confidence"
        assert result.confidence is not None, "异步评估结果必须有置信度"

    @pytest.mark.asyncio
    async def test_evaluate_async_score_zero_must_have_low_confidence(self):
        """
        标准：score=0时置信度必须≤0.3
        场景：异步评估返回score=0时，置信度应自动降低
        """
        evaluator = CodeEvaluator(client=None)

        request = EvaluationSchema(
            id="async_conf_002",
            type="code",
            payload={"code": "def hello()\n    return 'Hello'"},
        )

        result = await evaluator.evaluate_async(request)

        assert result.score == 0.0, f"语法错误应返回score=0.0，实际: {result.score}"
        assert result.confidence is not None, "异步评估结果必须有置信度"
        assert result.confidence <= 0.3, f"score=0时置信度必须≤0.3，实际: {result.confidence}"

    @pytest.mark.asyncio
    async def test_evaluate_sync_and_async_must_have_consistent_confidence(self):
        """
        标准：同步和异步评估路径应保持一致的置信度计算逻辑
        场景：相同输入应产生相同的置信度计算结果
        """
        evaluator = SecurityEvaluator(client=None)

        request = EvaluationSchema(
            id="async_conf_003",
            type="security",
            payload={"text": "测试文本"},
        )

        result_sync = evaluator.evaluate(request)
        result_async = await evaluator.evaluate_async(request)

        assert result_sync.confidence == result_async.confidence, "同步和异步路径应产生相同置信度"
