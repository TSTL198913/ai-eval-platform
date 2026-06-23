"""
RobustnessEvaluator 专项测试
测试目标：验证鲁棒性指数评估器的综合评估能力
关键发现：
- 权重归一化机制确保总权重为1.0
- 鲁棒性等级划分基于综合指数（excellent/good/acceptable/weak/poor）
- 各维度评分算法具有合理的默认值和边界处理
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.robustness_evaluator import RobustnessEvaluator
from src.schemas.evaluation import EvaluationSchema


@pytest.fixture(autouse=True)
def reset_evaluators_each_test():
    """
    自动在每个测试前重置 EvaluatorFactory 并重新触发自动发现。
    """
    from src.domain.evaluators import auto_discover
    from src.domain.evaluators.evaluator_factory import EvaluatorFactory as EF

    EF._registry = {}
    auto_discover(force=True)
    yield
    EF._registry = {}


@pytest.fixture
def evaluator():
    """创建评估器实例"""
    return RobustnessEvaluator()


@pytest.fixture
def mock_client():
    """创建Mock客户端"""
    client = MagicMock()
    client.call.return_value = "mocked_response"
    return client


# ============================================================
# Part 1: 正向测试 - 正常输入，预期正常输出
# ============================================================
class TestRobustnessEvaluatorPositiveCases:
    """正向测试 - 正常输入应返回预期输出"""

    def test_evaluate_robustness_with_all_dimensions(self, evaluator):
        """完整数据评估鲁棒性指数 - 应返回正确的综合评分"""
        # Arrange
        request = EvaluationSchema(
            id="test_001",
            type="robustness",
            payload={
                "action": "evaluate_robustness",
                "test_results": [
                    {"score": 0.9, "latency_ms": 100},
                    {"score": 0.85, "latency_ms": 110},
                    {"score": 0.88, "latency_ms": 105},
                ],
                "perturbation_results": [
                    {"survived": True, "type": "noise"},
                    {"survived": False, "score": 0.6, "type": "adversarial"},
                ],
                "security_results": {"total_tests": 10, "passed": 8},
                "drift_results": {"drift_score": 0.2},
                "weights": {
                    "consistency": 0.25,
                    "perturbation_resistance": 0.20,
                    "error_recovery": 0.15,
                    "security": 0.20,
                    "drift_resistance": 0.10,
                    "stability": 0.10,
                },
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert - 强断言验证业务逻辑
        assert result.data["is_valid"] is True
        assert "robustness_index" in result.data
        assert 0.0 <= result.data["robustness_index"] <= 1.0
        assert result.data["robustness_level"] in [
            "excellent",
            "good",
            "acceptable",
            "weak",
            "poor",
        ]
        assert "dimension_scores" in result.data
        assert len(result.data["dimension_scores"]) == 6
        assert "recommendations" in result.data
        assert result.status_code == 200

    def test_evaluate_robustness_with_default_weights(self, evaluator):
        """使用默认权重评估 - 应使用DEFAULT_WEIGHTS"""
        # Arrange
        request = EvaluationSchema(
            id="test_002",
            type="robustness",
            payload={
                "action": "evaluate_robustness",
                "test_results": [{"score": 0.9}, {"score": 0.9}],
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.data["is_valid"] is True
        assert result.data["weights"]["consistency"] == 0.25
        assert result.data["weights"]["perturbation_resistance"] == 0.20
        assert result.data["weights"]["security"] == 0.20

    def test_evaluate_perturbation_with_valid_results(self, evaluator):
        """评估扰动抵抗能力 - 应返回正确的分数和详情"""
        # Arrange
        request = EvaluationSchema(
            id="test_003",
            type="robustness",
            payload={
                "action": "perturbation_test",
                "perturbation_results": [
                    {"survived": True, "type": "noise"},
                    {"survived": True, "type": "noise"},
                    {"survived": False, "score": 0.5, "type": "adversarial"},
                ],
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.data["is_valid"] is True
        assert "perturbation_resistance_score" in result.data
        assert result.data["perturbation_resistance_score"] == pytest.approx(0.8333, rel=0.01)
        assert "details" in result.data
        assert result.data["details"]["total"] == 3
        assert result.data["details"]["survival_rate"] == pytest.approx(0.6667, rel=0.01)

    def test_evaluate_stability_with_valid_data(self, evaluator):
        """评估输出稳定性 - 应返回正确的稳定性分数"""
        # Arrange
        request = EvaluationSchema(
            id="test_004",
            type="robustness",
            payload={
                "action": "stability_score",
                "test_results": [
                    {"latency_ms": 100},
                    {"latency_ms": 105},
                    {"latency_ms": 98},
                    {"latency_ms": 102},
                ],
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.data["is_valid"] is True
        assert "stability_score" in result.data
        assert result.data["stability_score"] > 0.9  # 低方差应得高分
        assert result.data["test_count"] == 4

    def test_evaluate_error_recovery_with_valid_data(self, evaluator):
        """评估错误恢复能力 - 应返回正确的恢复率"""
        # Arrange
        request = EvaluationSchema(
            id="test_005",
            type="robustness",
            payload={
                "action": "error_recovery",
                "test_results": [
                    {"error": "timeout", "recovered": True},
                    {"error": "connection_failed", "recovered": True},
                    {"error": "rate_limit", "recovered": False},
                ],
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.data["is_valid"] is True
        assert "error_recovery_score" in result.data
        assert result.data["error_recovery_score"] == pytest.approx(0.6667, rel=0.01)


# ============================================================
# Part 2: 负向测试 - 错误输入，预期错误处理
# ============================================================
class TestRobustnessEvaluatorNegativeCases:
    """负向测试 - 错误输入应返回错误或合理默认值"""

    def test_evaluate_with_unknown_action(self, evaluator):
        """未知action - 应返回400错误"""
        # Arrange
        request = EvaluationSchema(
            id="test_006",
            type="robustness",
            payload={"action": "unknown_action"},
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.data["is_valid"] is False
        assert "Unknown action" in result.data["error"]
        assert result.status_code == 400

    def test_evaluate_robustness_with_empty_data(self, evaluator):
        """空数据评估 - 应返回中性默认分数"""
        # Arrange
        request = EvaluationSchema(
            id="test_007",
            type="robustness",
            payload={"action": "evaluate_robustness"},
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert - 空数据应返回合理的默认值
        assert result.data["is_valid"] is True
        assert result.data["robustness_index"] >= 0.5  # 默认分数应在中性范围
        assert result.data["robustness_level"] in ["acceptable", "good", "excellent"]

    def test_evaluate_perturbation_with_empty_results(self, evaluator):
        """空扰动结果 - 应返回中性分数0.5"""
        # Arrange
        request = EvaluationSchema(
            id="test_008",
            type="robustness",
            payload={
                "action": "perturbation_test",
                "perturbation_results": [],
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.data["is_valid"] is True
        assert result.data["perturbation_resistance_score"] == 0.5
        assert result.data["details"]["total"] == 0

    def test_evaluate_stability_with_insufficient_data(self, evaluator):
        """数据不足（<2个）评估稳定性 - 应返回默认值1.0"""
        # Arrange
        request = EvaluationSchema(
            id="test_009",
            type="robustness",
            payload={
                "action": "stability_score",
                "test_results": [{"latency_ms": 100}],
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.data["is_valid"] is True
        assert result.data["stability_score"] == 1.0  # 数据不足返回默认值


# ============================================================
# Part 3: 边界测试 - 边界值处理
# ============================================================
class TestRobustnessEvaluatorBoundaryCases:
    """边界测试 - 边界值应正确处理"""

    def test_calc_consistency_with_single_result(self, evaluator):
        """单个测试结果计算一致性 - 应返回1.0"""
        # Arrange
        test_results = [{"score": 0.9}]

        # Act
        consistency = evaluator._calc_consistency(test_results)

        # Assert
        assert consistency == 1.0

    def test_calc_consistency_with_zero_mean(self, evaluator):
        """均值为0计算一致性 - 应返回1.0（完全一致）

        【行为变更】原逻辑：mean=0时返回0.0，这是错误的。
        当所有分数都是0时，表示完全一致（std=0），应返回1.0。
        修复后：mean=0且std=0时返回1.0，mean=0且std!=0时返回0.5。
        """
        # Arrange
        test_results = [{"score": 0}, {"score": 0}, {"score": 0}]

        # Act
        consistency = evaluator._calc_consistency(test_results)

        # Assert - 所有分数相同（都是0），一致性应为1.0
        assert consistency == 1.0

    def test_calc_perturbation_resistance_with_no_scores(self, evaluator):
        """扰动结果无分数且未存活 - 应返回0.0"""
        # Arrange
        perturbation_results = [
            {"type": "noise"},
            {"type": "adversarial"},
        ]

        # Act
        score = evaluator._calc_perturbation_resistance(perturbation_results)

        # Assert
        assert score == 0.0

    def test_calc_error_recovery_with_no_errors(self, evaluator):
        """无错误案例计算恢复率 - 应返回1.0"""
        # Arrange
        test_results = [
            {"score": 0.9},
            {"score": 0.85},
        ]

        # Act
        recovery = evaluator._calc_error_recovery(test_results)

        # Assert
        assert recovery == 1.0

    def test_calc_security_score_with_zero_tests(self, evaluator):
        """安全测试数量为0 - 应返回中性分数0.5"""
        # Arrange
        security_results = {"total_tests": 0, "passed": 0}

        # Act
        score = evaluator._calc_security_score(security_results)

        # Assert
        assert score == 0.5

    def test_calc_drift_resistance_with_extreme_score(self, evaluator):
        """极端漂移分数（>1.0）计算抵抗能力 - 应返回0.0"""
        # Arrange
        drift_results = {"drift_score": 1.5}

        # Act
        resistance = evaluator._calc_drift_resistance(drift_results)

        # Assert
        assert resistance == 0.0


# ============================================================
# Part 4: 异常测试 - 异常情况处理
# ============================================================
class TestRobustnessEvaluatorExceptionCases:
    """异常测试 - 异常情况应正确处理"""

    def test_evaluate_with_exception_in_handler(self, evaluator):
        """处理器抛出异常 - 应捕获并返回500错误"""
        # Arrange
        request = EvaluationSchema(
            id="test_010",
            type="robustness",
            payload={
                "action": "evaluate_robustness",
                "test_results": "invalid_data_type",  # 类型错误会导致异常
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.data["is_valid"] is False
        assert "error" in result.data
        assert result.status_code == 500


# ============================================================
# Part 5: 依赖测试 - 外部依赖Mock验证
# ============================================================
class TestRobustnessEvaluatorDependencyHandling:
    """依赖测试 - 外部依赖Mock验证"""

    def test_evaluator_with_mock_client(self, mock_client):
        """使用Mock客户端创建评估器 - 应正确注入"""
        # Arrange & Act
        evaluator = RobustnessEvaluator(client=mock_client)

        # Assert
        assert evaluator.client is mock_client
        assert evaluator.client.call.return_value == "mocked_response"

    def test_evaluator_without_client(self):
        """无客户端创建评估器 - 应正常工作"""
        # Arrange & Act
        evaluator = RobustnessEvaluator(client=None)

        # Assert
        assert evaluator.client is None

        # 验证无客户端也能正常评估
        request = EvaluationSchema(
            id="test_011",
            type="robustness",
            payload={"action": "evaluate_robustness"},
        )
        result = evaluator.evaluate(request)
        assert result.data["is_valid"] is True

    def test_safe_evaluate_returns_same_as_evaluate(self, evaluator):
        """safe_evaluate方法 - 应与evaluate返回相同结果"""
        # Arrange
        request = EvaluationSchema(
            id="test_012",
            type="robustness",
            payload={"action": "evaluate_robustness"},
        )

        # Act
        result1 = evaluator.evaluate(request)
        result2 = evaluator.safe_evaluate(request)

        # Assert
        assert result1.data["is_valid"] == result2.data["is_valid"]
        assert result1.data["robustness_index"] == result2.data["robustness_index"]

    def test_weights_normalization(self, evaluator):
        """权重归一化 - 总权重不为1时应自动归一化"""
        # Arrange
        request = EvaluationSchema(
            id="test_013",
            type="robustness",
            payload={
                "action": "evaluate_robustness",
                "test_results": [{"score": 0.9}],
                "weights": {
                    "consistency": 0.3,
                    "perturbation_resistance": 0.3,
                    "error_recovery": 0.2,
                    "security": 0.2,
                    "drift_resistance": 0.1,
                    "stability": 0.1,
                },  # 总权重=1.2
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert - 权重应被归一化
        total_weight = sum(result.data["weights"].values())
        assert abs(total_weight - 1.0) < 0.01


# ============================================================
# Part 6: 鲁棒性等级划分测试
# ============================================================
class TestRobustnessLevelClassification:
    """鲁棒性等级划分测试 - 验证等级边界"""

    def test_robustness_level_excellent(self, evaluator):
        """鲁棒性指数>=0.9 - 应评为excellent"""
        # Arrange - 构造高分数据
        request = EvaluationSchema(
            id="test_014",
            type="robustness",
            payload={
                "action": "evaluate_robustness",
                "test_results": [{"score": 0.95}, {"score": 0.95}],
                "perturbation_results": [{"survived": True}],
                "security_results": {"total_tests": 10, "passed": 10},
                "drift_results": {"drift_score": 0.05},
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.data["robustness_index"] >= 0.9
        assert result.data["robustness_level"] == "excellent"

    def test_robustness_level_good(self, evaluator):
        """鲁棒性指数在[0.75, 0.9) - 应评为good"""
        # Arrange - 构造中等偏上数据，精确控制各维度分数
        request = EvaluationSchema(
            id="test_015",
            type="robustness",
            payload={
                "action": "evaluate_robustness",
                "test_results": [
                    {"score": 0.80, "latency_ms": 100},
                    {"score": 0.80, "latency_ms": 100},
                ],
                "perturbation_results": [
                    {"survived": True, "type": "noise"},
                    {"survived": False, "score": 0.6, "type": "adversarial"},
                ],
                "security_results": {"total_tests": 10, "passed": 7},
                "drift_results": {"drift_score": 0.25},
                "weights": {
                    "consistency": 0.25,
                    "perturbation_resistance": 0.20,
                    "error_recovery": 0.15,
                    "security": 0.20,
                    "drift_resistance": 0.10,
                    "stability": 0.10,
                },
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert 0.75 <= result.data["robustness_index"] < 0.9
        assert result.data["robustness_level"] == "good"

    def test_robustness_level_acceptable(self, evaluator):
        """鲁棒性指数在[0.6, 0.75) - 应评为acceptable"""
        # Arrange - 构造中等数据，精确控制各维度分数使综合分数约为0.68
        # consistency: 0.8 (score差异使变异系数为0.2)
        # perturbation_resistance: 0.5
        # error_recovery: 1.0 (无错误)
        # security: 0.5
        # drift_resistance: 0.5
        # stability: 0.8
        request = EvaluationSchema(
            id="test_016",
            type="robustness",
            payload={
                "action": "evaluate_robustness",
                "test_results": [
                    {"score": 0.52, "latency_ms": 100},
                    {"score": 0.78, "latency_ms": 120},
                ],
                "perturbation_results": [
                    {"survived": False, "score": 0.5, "type": "adversarial"},
                ],
                "security_results": {"total_tests": 10, "passed": 5},
                "drift_results": {"drift_score": 0.5},
                "weights": {
                    "consistency": 0.25,
                    "perturbation_resistance": 0.20,
                    "error_recovery": 0.15,
                    "security": 0.20,
                    "drift_resistance": 0.10,
                    "stability": 0.10,
                },
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert 0.6 <= result.data["robustness_index"] < 0.75
        assert result.data["robustness_level"] == "acceptable"

    def test_robustness_level_weak(self, evaluator):
        """鲁棒性指数在[0.4, 0.6) - 应评为weak"""
        # Arrange - 构造较差数据，精确控制各维度分数使综合分数约为0.5
        # consistency: 0.6
        # perturbation_resistance: 0.3
        # error_recovery: 1.0 (无错误)
        # security: 0.4
        # drift_resistance: 0.45
        # stability: 0.6
        request = EvaluationSchema(
            id="test_017",
            type="robustness",
            payload={
                "action": "evaluate_robustness",
                "test_results": [
                    {"score": 0.40, "latency_ms": 100},
                    {"score": 0.80, "latency_ms": 150},
                ],
                "perturbation_results": [
                    {"survived": False, "score": 0.3, "type": "adversarial"},
                ],
                "security_results": {"total_tests": 10, "passed": 4},
                "drift_results": {"drift_score": 0.55},
                "weights": {
                    "consistency": 0.25,
                    "perturbation_resistance": 0.20,
                    "error_recovery": 0.15,
                    "security": 0.20,
                    "drift_resistance": 0.10,
                    "stability": 0.10,
                },
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert 0.4 <= result.data["robustness_index"] < 0.6
        assert result.data["robustness_level"] == "weak"

    def test_robustness_level_poor(self, evaluator):
        """鲁棒性指数<0.4 - 应评为poor"""
        # Arrange - 构造很差数据，精确控制各维度分数使综合分数约为0.35
        # consistency: 0.5
        # perturbation_resistance: 0.1
        # error_recovery: 1.0 (无错误)
        # security: 0.2
        # drift_resistance: 0.15
        # stability: 0.5
        request = EvaluationSchema(
            id="test_018",
            type="robustness",
            payload={
                "action": "evaluate_robustness",
                "test_results": [
                    {"score": 0.30, "latency_ms": 100},
                    {"score": 0.70, "latency_ms": 200},
                ],
                "perturbation_results": [
                    {"survived": False, "score": 0.1, "type": "adversarial"},
                ],
                "security_results": {"total_tests": 10, "passed": 2},
                "drift_results": {"drift_score": 0.85},
                "weights": {
                    "consistency": 0.25,
                    "perturbation_resistance": 0.20,
                    "error_recovery": 0.15,
                    "security": 0.20,
                    "drift_resistance": 0.10,
                    "stability": 0.10,
                },
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.data["robustness_index"] < 0.4
        assert result.data["robustness_level"] == "poor"


# ============================================================
# Part 7: 改进建议生成测试
# ============================================================
class TestRecommendationGeneration:
    """改进建议生成测试 - 验证建议逻辑"""

    def test_generate_recommendations_for_low_consistency(self, evaluator):
        """一致性分数低于0.7 - 应生成一致性改进建议"""
        # Arrange
        scores = {
            "consistency": 0.5,
            "perturbation_resistance": 0.8,
            "error_recovery": 0.8,
            "security": 0.8,
            "drift_resistance": 0.8,
            "stability": 0.8,
        }

        # Act
        recommendations = evaluator._generate_recommendations(scores)

        # Assert
        assert any("一致性" in r for r in recommendations)

    def test_generate_recommendations_for_low_security(self, evaluator):
        """安全性分数低于0.7 - 应生成安全改进建议"""
        # Arrange
        scores = {
            "consistency": 0.8,
            "perturbation_resistance": 0.8,
            "error_recovery": 0.8,
            "security": 0.5,
            "drift_resistance": 0.8,
            "stability": 0.8,
        }

        # Act
        recommendations = evaluator._generate_recommendations(scores)

        # Assert
        assert any("安全" in r for r in recommendations)

    def test_generate_recommendations_for_all_high_scores(self, evaluator):
        """所有分数都高 - 应生成良好状态建议"""
        # Arrange
        scores = {
            "consistency": 0.9,
            "perturbation_resistance": 0.9,
            "error_recovery": 0.9,
            "security": 0.9,
            "drift_resistance": 0.9,
            "stability": 0.9,
        }

        # Act
        recommendations = evaluator._generate_recommendations(scores)

        # Assert
        assert any("良好" in r or "监控" in r for r in recommendations)


# ============================================================
# Part 8: 扰动分析测试
# ============================================================
class TestPerturbationAnalysis:
    """扰动分析测试 - 验证扰动结果分析逻辑"""

    def test_analyze_perturbations_with_multiple_types(self, evaluator):
        """多种类型扰动分析 - 应正确统计各类型"""
        # Arrange
        perturbation_results = [
            {"type": "noise", "survived": True},
            {"type": "noise", "survived": False},
            {"type": "adversarial", "survived": True},
            {"type": "typo", "survived": True},
        ]

        # Act
        details = evaluator._analyze_perturbations(perturbation_results)

        # Assert
        assert details["total"] == 4
        assert details["survival_rate"] == 0.75
        assert details["by_type"]["noise"]["total"] == 2
        assert details["by_type"]["noise"]["survived"] == 1
        assert details["by_type"]["adversarial"]["survived"] == 1

    def test_analyze_perturbations_with_empty_results(self, evaluator):
        """空扰动结果分析 - 应返回空统计"""
        # Arrange
        perturbation_results = []

        # Act
        details = evaluator._analyze_perturbations(perturbation_results)

        # Assert
        assert details["total"] == 0


# ============================================================
# Part 9: 工厂注册测试
# ============================================================
class TestEvaluatorFactoryRegistration:
    """工厂注册测试 - 验证评估器正确注册"""

    def test_evaluator_registered_in_factory(self):
        """评估器应正确注册到工厂"""
        # Arrange & Act
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory

        # Assert
        assert "robustness" in EvaluatorFactory.list_evaluators()

    def test_factory_creates_robustness_evaluator(self):
        """工厂应能创建RobustnessEvaluator实例"""
        # Arrange & Act
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory

        evaluator = EvaluatorFactory.get("robustness")

        # Assert
        assert type(evaluator).__name__ == "RobustnessEvaluator"
        assert hasattr(evaluator, "evaluate")
        assert hasattr(evaluator, "safe_evaluate")
