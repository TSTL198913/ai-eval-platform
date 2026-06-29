"""
RobustnessEvaluator 专项测试
测试目标：验证 RobustnessEvaluator 的鲁棒性评估功能
关键发现：评估器采用多维度加权评分，包含一致性、扰动抵抗、错误恢复、安全性、漂移抵抗和稳定性六个维度
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.robustness_evaluator import RobustnessEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestRobustnessEvaluatorPositiveCases:
    """正向测试 - 正常输入"""

    @pytest.fixture
    def target(self):
        return RobustnessEvaluator()

    def test_evaluate_robustness_with_normal_data(self, target):
        """正常test_results应返回有效的鲁棒性指数"""
        request = EvaluationSchema(
            id="test_001",
            type="robustness",
            payload={
                "action": "evaluate_robustness",
                "test_results": [
                    {"input": "test1", "output": "result1", "score": 0.9},
                    {"input": "test2", "output": "result2", "score": 0.85},
                    {"input": "test3", "output": "result3", "score": 0.88},
                ],
                "perturbation_results": [
                    {"type": "typo", "survived": True},
                    {"type": "case", "survived": True},
                ],
                "security_results": {"total_tests": 10, "passed": 9},
                "drift_results": {"drift_score": 0.1},
            },
        )

        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.data["is_valid"] is True
        assert "robustness_index" in result.data
        assert result.data["robustness_index"] >= 0.7
        assert "robustness_level" in result.data

    def test_evaluate_perturbation_resistance(self, target):
        """扰动测试应返回扰动抵抗分数"""
        request = EvaluationSchema(
            id="test_002",
            type="robustness",
            payload={
                "action": "perturbation_test",
                "perturbation_results": [
                    {"type": "typo", "survived": True, "score": 1.0},
                    {"type": "case", "survived": True, "score": 1.0},
                    {"type": "noise", "survived": False, "score": 0.5},
                ],
            },
        )

        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.data["is_valid"] is True
        assert "perturbation_resistance_score" in result.data
        assert 0.0 <= result.data["perturbation_resistance_score"] <= 1.0

    def test_evaluate_stability_score(self, target):
        """稳定性评分应正确计算"""
        request = EvaluationSchema(
            id="test_003",
            type="robustness",
            payload={
                "action": "stability_score",
                "test_results": [
                    {"latency_ms": 100},
                    {"latency_ms": 110},
                    {"latency_ms": 105},
                    {"latency_ms": 95},
                ],
            },
        )

        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.data["is_valid"] is True
        assert "stability_score" in result.data
        assert result.data["test_count"] == 4

    def test_evaluate_error_recovery(self, target):
        """错误恢复评分应正确计算"""
        request = EvaluationSchema(
            id="test_004",
            type="robustness",
            payload={
                "action": "error_recovery",
                "test_results": [
                    {"error": "timeout", "recovered": True},
                    {"error": "network", "recovered": True},
                    {"status": "error", "recovered": False},
                ],
            },
        )

        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.data["is_valid"] is True
        assert "error_recovery_score" in result.data
        assert result.data["error_recovery_score"] == pytest.approx(2 / 3, rel=0.01)


class TestRobustnessEvaluatorNegativeCases:
    """负向测试 - 错误输入"""

    @pytest.fixture
    def target(self):
        return RobustnessEvaluator()

    def test_empty_test_results_uses_defaults(self, target):
        """空test_results应使用默认权重计算"""
        request = EvaluationSchema(
            id="test_005",
            type="robustness",
            payload={
                "action": "evaluate_robustness",
                "test_results": [],
                "perturbation_results": [],
                "security_results": {},
                "drift_results": {},
            },
        )

        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.data["is_valid"] is True
        assert "robustness_index" in result.data

    def test_no_perturbation_results_returns_neutral(self, target):
        """无perturbation_results应返回中性分数0.5"""
        request = EvaluationSchema(
            id="test_006",
            type="robustness",
            payload={
                "action": "evaluate_robustness",
                "test_results": [
                    {"score": 0.9},
                ],
                "perturbation_results": [],
                "security_results": {},
                "drift_results": {},
            },
        )

        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.data["dimension_scores"]["perturbation_resistance"] == 0.5

    def test_unknown_action_returns_error(self, target):
        """未知action应返回错误"""
        request = EvaluationSchema(
            id="test_007",
            type="robustness",
            payload={
                "action": "unknown_action",
            },
        )

        result = target.evaluate(request)

        # 错误信息在data中，DomainResponse的is_valid默认是True
        assert result.data["is_valid"] is False
        assert "Unknown action" in result.data["error"]


class TestRobustnessEvaluatorBoundaryCases:
    """边界测试 - 边界值"""

    @pytest.fixture
    def target(self):
        return RobustnessEvaluator()

    def test_single_test_result_returns_full_consistency(self, target):
        """单个test_result应返回一致性满分"""
        request = EvaluationSchema(
            id="test_008",
            type="robustness",
            payload={
                "action": "evaluate_robustness",
                "test_results": [{"score": 0.9}],
                "perturbation_results": [],
                "security_results": {},
                "drift_results": {},
            },
        )

        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.data["dimension_scores"]["consistency"] == 1.0

    def test_all_survived_perturbations(self, target):
        """全部survived的扰动测试应得满分"""
        request = EvaluationSchema(
            id="test_009",
            type="robustness",
            payload={
                "action": "perturbation_test",
                "perturbation_results": [
                    {"survived": True},
                    {"survived": True},
                    {"survived": True},
                ],
            },
        )

        result = target.evaluate(request)

        assert result.data["perturbation_resistance_score"] == 1.0

    def test_no_error_cases_returns_full_recovery(self, target):
        """无错误案例应返回恢复能力满分"""
        request = EvaluationSchema(
            id="test_010",
            type="robustness",
            payload={
                "action": "error_recovery",
                "test_results": [
                    {"score": 0.9},
                    {"score": 0.85},
                ],
            },
        )

        result = target.evaluate(request)

        assert result.data["error_recovery_score"] == 1.0

    def test_weight_normalization(self, target):
        """权重总和不为1时应自动归一化"""
        request = EvaluationSchema(
            id="test_011",
            type="robustness",
            payload={
                "action": "evaluate_robustness",
                "test_results": [{"score": 0.9}],
                "weights": {
                    "consistency": 0.5,
                    "perturbation_resistance": 0.5,
                    "error_recovery": 0.5,
                    "security": 0.5,
                    "drift_resistance": 0.5,
                    "stability": 0.5,
                },
            },
        )

        result = target.evaluate(request)

        weights = result.data["weights"]
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.01


class TestRobustnessEvaluatorAlgorithmTests:
    """评分算法测试"""

    @pytest.fixture
    def target(self):
        return RobustnessEvaluator()

    def test_consistency_calculation_low_variance(self, target):
        """低方差应产生高一致性分数"""
        test_results = [
            {"score": 0.9},
            {"score": 0.89},
            {"score": 0.91},
        ]
        consistency = target._calc_consistency(test_results)

        assert consistency > 0.9

    def test_consistency_calculation_high_variance(self, target):
        """高方差应产生低一致性分数"""
        test_results = [
            {"score": 0.9},
            {"score": 0.5},
            {"score": 0.1},
        ]
        consistency = target._calc_consistency(test_results)

        assert consistency < 0.5

    def test_perturbation_resistance_mixed_results(self, target):
        """混合survived结果应正确计算平均分"""
        perturbation_results = [
            {"survived": True},
            {"survived": False, "score": 0.3},
            {"survived": True},
        ]
        score = target._calc_perturbation_resistance(perturbation_results)

        assert score == pytest.approx(0.767, rel=0.01)

    def test_security_score_calculation(self, target):
        """安全性分数应正确计算passed/total"""
        security_results = {"total_tests": 20, "passed": 18}
        score = target._calc_security_score(security_results)

        assert score == 0.9

    def test_drift_resistance_inverse_score(self, target):
        """漂移抵抗应为1-drift_score"""
        drift_results = {"drift_score": 0.2}
        score = target._calc_drift_resistance(drift_results)

        assert score == 0.8

    def test_robustness_level_classification(self, target):
        """鲁棒性等级分类应正确"""
        # 设置权重使得最终分数明确落在目标范围内
        test_cases = [
            (0.95, "excellent"),
            (0.80, "good"),
            (0.65, "acceptable"),
            (0.50, "weak"),
            (0.35, "poor"),
        ]
        for score, expected_level in test_cases:
            request = EvaluationSchema(
                id=f"test_level_{score}",
                type="robustness",
                payload={
                    "action": "evaluate_robustness",
                    "test_results": [{"score": 0.9}],
                    "perturbation_results": [{"survived": True}],
                    "security_results": {"total_tests": 10, "passed": int(score * 10)},
                    "drift_results": {"drift_score": 1 - score},
                    "weights": {
                        "consistency": 0.0,
                        "perturbation_resistance": 0.0,
                        "error_recovery": 0.0,
                        "security": score,
                        "drift_resistance": 0.0,
                        "stability": 0.0,
                    },
                },
            )
            result = target.evaluate(request)
            assert result.data["robustness_level"] == expected_level, (
                f"score={score}, expected={expected_level}, actual={result.data['robustness_level']}"
            )

    def test_stability_with_zero_mean_returns_zero(self, target):
        """latency为0时应返回稳定性0分"""
        test_results = [
            {"latency_ms": 0},
            {"latency_ms": 0},
        ]
        stability = target._calc_stability(test_results)

        assert stability == 0.0

    def test_perturbation_empty_returns_neutral(self, target):
        """空perturbation_results应返回0.5"""
        score = target._calc_perturbation_resistance([])

        assert score == 0.5

    def test_security_empty_results_returns_neutral(self, target):
        """空security_results应返回0.5"""
        score = target._calc_security_score({})

        assert score == 0.5

    def test_recommendations_generation(self, target):
        """建议生成应基于低分维度"""
        request = EvaluationSchema(
            id="test_rec",
            type="robustness",
            payload={
                "action": "evaluate_robustness",
                "test_results": [{"score": 0.3}],
                "perturbation_results": [{"survived": False}],
                "security_results": {"total_tests": 10, "passed": 2},
                "drift_results": {"drift_score": 0.8},
            },
        )

        result = target.evaluate(request)

        assert "recommendations" in result.data
        assert len(result.data["recommendations"]) > 0
