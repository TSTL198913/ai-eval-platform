from unittest.mock import MagicMock, patch

from src.domain.evaluators.drift import DriftDetectionEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestDriftDetectionEvaluator:
    """行为漂移检测评估器测试"""

    def setup_method(self):
        self.mock_client = MagicMock()

    def test_evaluate_similarity_detection(self):
        """测试基于相似度的漂移检测"""
        evaluator = DriftDetectionEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_drift",
            type="drift",
            payload={
                "user_input": "测试问题",
                "actual_output": "新的回答内容",
                "baseline_output": "原始基准回答",
                "methods": ["similarity"],
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert "similarity" in result.data["methods"]

    def test_evaluate_similarity_no_drift(self):
        """测试无漂移情况"""
        evaluator = DriftDetectionEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_no_drift",
            type="drift",
            payload={
                "user_input": "测试问题",
                "actual_output": "完全相同的回答",
                "baseline_output": "完全相同的回答",
                "methods": ["similarity"],
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["drift_detected"] is False

    def test_evaluate_statistical_detection(self):
        """测试基于统计的漂移检测"""
        evaluator = DriftDetectionEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_stat",
            type="drift",
            payload={
                "user_input": "测试问题",
                "actual_output": "简短回答",
                "baseline_output": "一个非常长的基准回答内容",
                "methods": ["statistical"],
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert "statistical" in result.data["methods"]

    def test_evaluate_score_comparison(self):
        """测试基于分数历史的漂移检测"""
        with patch("src.domain.evaluators.drift.EvaluationRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_recent.return_value = []

            evaluator = DriftDetectionEvaluator(self.mock_client)
            request = EvaluationSchema(
                id="test_score",
                type="drift",
                payload={
                    "user_input": "测试问题",
                    "actual_output": "回答",
                    "methods": ["score_comparison"],
                },
            )

            result = evaluator.evaluate(request)

            assert result.is_valid is True

    def test_evaluate_missing_user_input(self):
        """测试缺少输入"""
        evaluator = DriftDetectionEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_missing",
            type="drift",
            payload={"actual_output": "回答"},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "不能为空" in result.error

    def test_evaluate_missing_actual_output(self):
        """测试缺少实际输出"""
        evaluator = DriftDetectionEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_missing",
            type="drift",
            payload={"user_input": "测试问题"},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "不能为空" in result.error

    def test_calculate_confidence(self):
        """测试置信度计算"""
        evaluator = DriftDetectionEvaluator(self.mock_client)
        results = {
            "method1": {"confidence": 0.8},
            "method2": {"confidence": 0.6},
        }
        confidence = evaluator._calculate_confidence(results)

        assert confidence == 0.7

    def test_calculate_confidence_empty(self):
        """测试空结果置信度"""
        evaluator = DriftDetectionEvaluator(self.mock_client)
        confidence = evaluator._calculate_confidence({})

        assert confidence == 0.5