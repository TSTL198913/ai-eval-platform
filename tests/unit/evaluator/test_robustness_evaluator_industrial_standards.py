"""
RobustnessEvaluator 2026年工业级标准合规性测试
测试目标：验证ERROR状态下score必须为0.0、必须包含confidence_level和confidence_components
标准依据：2026年AI评测工业级标准 - 评分合理性原则、置信度完整性原则
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.robustness_evaluator import RobustnessEvaluator
from src.schemas.evaluation import EvaluationSchema, EvaluatorStatus


class TestRobustnessEvaluatorIndustrialStandards:
    """2026年工业级标准合规性测试"""

    @pytest.fixture
    def evaluator(self):
        return RobustnessEvaluator(client=None)

    def test_error_status_must_return_zero_score_for_unknown_action(self, evaluator):
        """
        标准：ERROR状态必须返回score=0.0，禁止score=None
        场景：未知的action
        """
        request = EvaluationSchema(
            id="robust_std_001",
            type="robustness",
            payload={
                "action": "unknown_action",
            },
        )

        result = evaluator.evaluate(request)

        assert result.evaluation_status == EvaluatorStatus.ERROR
        assert result.score == 0.0, f"ERROR状态应返回score=0.0，实际返回: {result.score}"
        assert result.is_valid is False

    def test_error_status_must_have_confidence_level(self, evaluator):
        """
        标准：ERROR状态必须包含confidence_level
        场景：未知的action
        """
        request = EvaluationSchema(
            id="robust_std_002",
            type="robustness",
            payload={
                "action": "unknown_action",
            },
        )

        result = evaluator.evaluate(request)

        assert result.evaluation_status == EvaluatorStatus.ERROR
        assert hasattr(result, "confidence_level"), "ERROR状态必须包含confidence_level"
        assert result.confidence_level is not None, "confidence_level不能为空"

    def test_error_status_must_have_confidence_components(self, evaluator):
        """
        标准：ERROR状态必须包含confidence_auto_computed和confidence_components
        场景：未知的action
        """
        request = EvaluationSchema(
            id="robust_std_003",
            type="robustness",
            payload={
                "action": "unknown_action",
            },
        )

        result = evaluator.evaluate(request)

        assert result.evaluation_status == EvaluatorStatus.ERROR
        assert result.data is not None, "ERROR状态必须包含data字段"
        assert "confidence_auto_computed" in result.data, "ERROR状态必须包含confidence_auto_computed标记"
        assert "confidence_components" in result.data, "ERROR状态必须包含confidence_components"

    def test_error_status_must_have_confidence(self, evaluator):
        """
        标准：ERROR状态必须包含confidence，且在0-1范围内
        场景：未知的action
        """
        request = EvaluationSchema(
            id="robust_std_004",
            type="robustness",
            payload={
                "action": "unknown_action",
            },
        )

        result = evaluator.evaluate(request)

        assert result.evaluation_status == EvaluatorStatus.ERROR
        assert result.confidence is not None, "ERROR状态必须包含confidence"
        assert 0.0 <= result.confidence <= 1.0, f"confidence应在[0,1]区间，实际: {result.confidence}"

    def test_exception_handling_must_return_zero_score(self, evaluator):
        """
        标准：异常处理返回的ERROR状态必须返回score=0.0
        场景：传入无效数据导致异常
        """
        request = EvaluationSchema(
            id="robust_std_005",
            type="robustness",
            payload={
                "action": "evaluate_robustness",
                "test_results": "not_a_list",
            },
        )

        result = evaluator.evaluate(request)

        assert result.evaluation_status == EvaluatorStatus.ERROR
        assert result.score == 0.0, f"ERROR状态应返回score=0.0，实际返回: {result.score}"

    def test_success_status_must_have_numeric_score(self, evaluator):
        """
        标准：SUCCESS状态必须返回明确的数值score
        场景：有效数据
        """
        request = EvaluationSchema(
            id="robust_std_006",
            type="robustness",
            payload={
                "action": "evaluate_robustness",
                "test_results": [{"score": 0.9}, {"score": 0.8}, {"score": 0.95}],
            },
        )

        result = evaluator.evaluate(request)

        assert result.score is not None, "有效数据评估应返回明确的score"
        assert isinstance(result.score, (int, float)), f"score应为数值类型，实际类型: {type(result.score)}"
        assert 0.0 <= result.score <= 1.0, f"score应在[0,1]区间，实际: {result.score}"