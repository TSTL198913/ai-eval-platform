"""
CompositeEvaluator 2026年工业级标准合规性测试
测试目标：验证状态判断应基于evaluation_status而非is_valid
标准依据：2026年AI评测工业级标准 - is_valid废弃原则
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.composite import CompositeEvaluator, EvaluatorChainConfig
from src.domain.evaluators.security import SecurityEvaluator
from src.domain.evaluators.general import GeneralEvaluator
from src.schemas.evaluation import EvaluationSchema, EvaluatorStatus
from tests.utils.test_helpers import approx_score
from unittest.mock import MagicMock, patch


class TestCompositeEvaluatorIndustrialStandards:
    """2026年工业级标准合规性测试 - is_valid废弃"""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.chat.return_value = "评估完成"
        return client

    def test_success_status_should_contribute_to_score(self, mock_client):
        """
        标准：SUCCESS状态应参与加权计算
        场景：子评估器返回SUCCESS时，应正常参与计算
        """
        mock_success = MagicMock()
        mock_success.safe_evaluate.return_value = MagicMock(
            evaluation_status=EvaluatorStatus.SUCCESS,
            score=0.8,
            is_valid=True,
            error=None,
            data={"dimensions_evaluated": ["test_dim"]},
            metadata={},
        )

        evaluator = CompositeEvaluator(
            evaluators=[EvaluatorChainConfig("mock_eval", weight=1.0)],
            client=mock_client,
        )

        with patch("src.domain.evaluators.evaluator_factory.EvaluatorFactory.get", return_value=mock_success):
            request = EvaluationSchema(
                id="comp_std_001",
                type="composite",
                payload={"text": "测试文本"},
            )

            result = evaluator.evaluate(request)

            assert result.evaluation_status in [EvaluatorStatus.SUCCESS, EvaluatorStatus.PARTIAL]
            assert result.score is not None, "组合评估应返回明确的score"
            assert result.score == approx_score(0.8), "SUCCESS状态应贡献全部分数"

    def test_error_status_should_not_contribute_to_score(self, mock_client):
        """
        标准：ERROR状态不应参与加权计算，score应为0.0
        场景：子评估器返回ERROR时，组合评估应正确处理
        """
        mock_error = MagicMock()
        mock_error.safe_evaluate.return_value = MagicMock(
            evaluation_status=EvaluatorStatus.ERROR,
            score=0.0,
            is_valid=False,
            error="安全违规",
            data={},
            metadata={},
        )

        evaluator = CompositeEvaluator(
            evaluators=[EvaluatorChainConfig("mock_eval", weight=1.0)],
            client=mock_client,
        )

        with patch("src.domain.evaluators.evaluator_factory.EvaluatorFactory.get", return_value=mock_error):
            request = EvaluationSchema(
                id="comp_std_002",
                type="composite",
                payload={"text": "恶意代码"},
            )

            result = evaluator.evaluate(request)

            assert result.score is not None, "组合评估应返回明确的score"
            assert result.score == 0.0, "ERROR状态应返回0分"

    def test_partial_status_should_contribute_to_score(self, mock_client):
        """
        标准：PARTIAL状态应参与加权计算
        场景：子评估器返回PARTIAL时，应正常参与计算
        """
        mock_partial = MagicMock()
        mock_partial.safe_evaluate.return_value = MagicMock(
            evaluation_status=EvaluatorStatus.PARTIAL,
            score=0.5,
            is_valid=True,
            error=None,
            data={"dimensions_evaluated": ["test_dim"], "dimensions_skipped": ["skipped_dim"]},
            metadata={},
        )

        evaluator = CompositeEvaluator(
            evaluators=[EvaluatorChainConfig("mock_eval", weight=1.0)],
            client=mock_client,
        )

        with patch("src.domain.evaluators.evaluator_factory.EvaluatorFactory.get", return_value=mock_partial):
            request = EvaluationSchema(
                id="comp_std_003",
                type="composite",
                payload={"text": "测试文本"},
            )

            result = evaluator.evaluate(request)

            assert result.score is not None, "组合评估应返回明确的score"
            assert result.score == approx_score(0.5), "PARTIAL状态应贡献分数"

    def test_cannot_evaluate_status_should_not_contribute(self, mock_client):
        """
        标准：CANNOT_EVALUATE状态应返回CANNOT_EVALUATE状态
        场景：子评估器返回CANNOT_EVALUATE时，组合评估也应返回CANNOT_EVALUATE
        """
        mock_cannot_eval = MagicMock()
        mock_cannot_eval.safe_evaluate.return_value = MagicMock(
            evaluation_status=EvaluatorStatus.CANNOT_EVALUATE,
            score=None,
            is_valid=False,
            error="无法评估",
            data={},
            metadata={},
        )

        evaluator = CompositeEvaluator(
            evaluators=[EvaluatorChainConfig("mock_eval", weight=1.0)],
            client=mock_client,
        )

        with patch("src.domain.evaluators.evaluator_factory.EvaluatorFactory.get", return_value=mock_cannot_eval):
            request = EvaluationSchema(
                id="comp_std_004",
                type="composite",
                payload={"text": "测试文本"},
            )

            result = evaluator.evaluate(request)

            assert result.evaluation_status == EvaluatorStatus.CANNOT_EVALUATE, \
                f"CANNOT_EVALUATE状态应返回CANNOT_EVALUATE，实际: {result.evaluation_status}"

    def test_mixed_statuses_should_calculate_correctly(self, mock_client):
        """
        标准：混合状态应正确计算加权分数
        场景：SUCCESS(0.8, 0.5权重) + ERROR(0.0, 0.5权重) = 0.0（ERROR状态一票否决）
        """
        mock_success = MagicMock()
        mock_success.safe_evaluate.return_value = MagicMock(
            evaluation_status=EvaluatorStatus.SUCCESS,
            score=0.8,
            is_valid=True,
            error=None,
            data={},
            metadata={},
        )

        mock_error = MagicMock()
        mock_error.safe_evaluate.return_value = MagicMock(
            evaluation_status=EvaluatorStatus.ERROR,
            score=0.0,
            is_valid=False,
            error="错误",
            data={},
            metadata={},
        )

        evaluator = CompositeEvaluator(
            evaluators=[
                EvaluatorChainConfig("success_eval", weight=0.5),
                EvaluatorChainConfig("error_eval", weight=0.5),
            ],
            client=mock_client,
        )

        def get_mock_evaluator(evaluator_type, client=None):
            if evaluator_type == "success_eval":
                return mock_success
            return mock_error

        with patch("src.domain.evaluators.evaluator_factory.EvaluatorFactory.get", side_effect=get_mock_evaluator):
            request = EvaluationSchema(
                id="comp_std_005",
                type="composite",
                payload={"text": "测试文本"},
            )

            result = evaluator.evaluate(request)

            assert result.score is not None, "组合评估应返回明确的score"
            assert result.score == 0.0, f"ERROR状态应返回0分，实际: {result.score}"
