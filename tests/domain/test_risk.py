"""
RiskEvaluator 专项测试
测试目标：验证迭代优化风险评估器的风险检测逻辑
关键发现：
- 风险评分计算使用加权公式
- 风险等级基于阈值判断（high/medium/low）
- 支持单一风险检测和综合风险检测
"""

import pytest
from unittest.mock import MagicMock

from src.domain.evaluators.risk import RiskEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.schemas.evaluation import DomainResponse, EvaluationSchema


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


# ============================================================
# Part 1: 正向测试 - 正常输入
# ============================================================
class TestRiskEvaluatorPositiveCases:
    """正向测试 - 验证正常输入返回预期输出"""

    @pytest.fixture
    def evaluator(self):
        """创建评估器实例"""
        return RiskEvaluator()

    def test_detect_all_returns_comprehensive_risk_assessment(self, evaluator):
        """综合风险检测应返回所有风险类型的评估结果"""
        # Arrange
        request = EvaluationSchema(
            id="test-001",
            type="risk",
            payload={
                "action": "detect_all",
                "feature_complexity": 0.3,
                "core_alignment": 0.9,
                "unresolved_warnings": 10,
                "overall_coverage": 0.85,
            }
        )
        
        # Act
        result = evaluator.evaluate(request)
        
        # Assert - 强断言验证业务逻辑
        assert result.is_valid is True
        assert result.score is not None
        assert 0.0 <= result.score <= 1.0
        assert "overall_risk_level" in result.data
        assert result.data["overall_risk_level"] in ("low", "medium", "high")
        assert "high_risks" in result.data
        assert "medium_risks" in result.data
        assert "details" in result.data
        # 验证所有风险类型都被检测
        assert "feature_creep" in result.data["details"]
        assert "tech_debt" in result.data["details"]
        assert "coupling" in result.data["details"]
        assert "test_coverage" in result.data["details"]
        assert "drift" in result.data["details"]

    def test_feature_creep_detection_with_high_risk(self, evaluator):
        """功能蔓延检测 - 高风险场景"""
        # Arrange - 高功能复杂度、低核心对齐度
        request = EvaluationSchema(
            id="test-002",
            type="risk",
            payload={
                "action": "feature_creep",
                "feature_complexity": 0.9,  # 高复杂度
                "core_alignment": 0.3,      # 低对齐度
                "responsibility_blur": 0.8  # 高职责模糊
            }
        )
        
        # Act
        result = evaluator.evaluate(request)
        
        # Assert - 强断言
        assert result.is_valid is True
        assert result.data["risk_type"] == "feature_creep"
        assert result.data["risk_level"] == "high"
        assert result.data["risk_score"] > 0.7
        assert result.score < 0.3  # score = 1.0 - risk_score
        assert "建议审查新增功能" in result.data["suggestion"]

    def test_tech_debt_detection_with_medium_risk(self, evaluator):
        """技术债务检测 - 中风险场景"""
        # Arrange - 中等技术债务
        request = EvaluationSchema(
            id="test-003",
            type="risk",
            payload={
                "action": "tech_debt",
                "unresolved_warnings": 50,        # 中等警告数
                "duplicate_code_ratio": 0.3,      # 中等重复率
                "pending_refactoring": 5,         # 中等重构数
                "documentation_gap": 0.4          # 中等文档缺失
            }
        )
        
        # Act
        result = evaluator.evaluate(request)
        
        # Assert - 强断言
        assert result.is_valid is True
        assert result.data["risk_type"] == "tech_debt"
        assert result.data["risk_level"] in ("medium", "high")
        assert 0.0 <= result.data["risk_score"] <= 1.0
        assert "metrics" in result.data
        assert result.data["metrics"]["unresolved_warnings"] == 50

    def test_coupling_detection_with_low_risk(self, evaluator):
        """模块耦合检测 - 低风险场景"""
        # Arrange - 低耦合（确保风险评分低于0.25）
        request = EvaluationSchema(
            id="test-004",
            type="risk",
            payload={
                "action": "coupling",
                "external_dependencies": 1,    # 极少外部依赖
                "cyclic_dependencies": 0,      # 无循环依赖
                "cross_layer_calls": 0         # 无跨层调用
            }
        )
        
        # Act
        result = evaluator.evaluate(request)
        
        # Assert - 强断言
        assert result.is_valid is True
        assert result.data["risk_type"] == "coupling"
        assert result.data["risk_level"] == "low"
        # min(1/10, 1) * 0.5 = 0.05
        assert result.data["risk_score"] < 0.25
        assert result.score > 0.75
        assert "模块耦合度控制良好" in result.data["suggestion"]

    def test_test_coverage_detection_with_high_risk(self, evaluator):
        """测试覆盖检测 - 高风险场景（覆盖率不足）"""
        # Arrange - 极低覆盖率（确保风险评分 >= 0.5）
        request = EvaluationSchema(
            id="test-005",
            type="risk",
            payload={
                "action": "test_coverage",
                "overall_coverage": 0.2,        # 极低整体覆盖率
                "new_code_coverage": 0.1,       # 极低新代码覆盖率
                "critical_path_coverage": 0.2,  # 极低关键路径覆盖率
                "test_pass_rate": 0.5           # 低通过率
            }
        )
        
        # Act
        result = evaluator.evaluate(request)
        
        # Assert - 强断言
        assert result.is_valid is True
        assert result.data["risk_type"] == "test_coverage"
        # 计算风险评分: (0.8-0.2)*0.25 + (0.8-0.1)*0.35 + (0.8-0.2)*0.25 + (1-0.5)*0.15
        # = 0.15 + 0.245 + 0.15 + 0.075 = 0.52
        assert result.data["risk_level"] == "high"
        assert result.data["risk_score"] >= 0.5
        assert "建议补充测试用例" in result.data["suggestion"]

    def test_drift_detection_with_significant_drift(self, evaluator):
        """行为漂移检测 - 显著漂移场景"""
        # Arrange - 明显的分数漂移
        request = EvaluationSchema(
            id="test-006",
            type="risk",
            payload={
                "action": "drift",
                "baseline_score": 0.9,          # 基线分数
                "current_score": 0.5,           # 当前分数（显著下降）
                "format_changes": 8,           # 格式变化
                "latency_increase": 50,         # 延迟增加
                "error_rate_change": 0.05      # 错误率变化
            }
        )
        
        # Act
        result = evaluator.evaluate(request)
        
        # Assert - 强断言
        assert result.is_valid is True
        assert result.data["risk_type"] == "drift"
        assert result.data["risk_level"] in ("medium", "high")
        assert result.data["metrics"]["score_drift"] == 0.4  # abs(0.9 - 0.5)
        assert result.data["risk_score"] > 0.2


# ============================================================
# Part 2: 负向测试 - 错误输入
# ============================================================
class TestRiskEvaluatorNegativeCases:
    """负向测试 - 验证错误输入的错误处理"""

    @pytest.fixture
    def evaluator(self):
        return RiskEvaluator()

    def test_unknown_action_returns_error(self, evaluator):
        """未知 action 应返回错误"""
        # Arrange
        request = EvaluationSchema(
            id="test-007",
            type="risk",
            payload={
                "action": "unknown_action_xyz"
            }
        )
        
        # Act
        result = evaluator.evaluate(request)
        
        # Assert - 强断言
        assert result.is_valid is False
        assert result.error is not None
        assert "Unknown risk detection action" in result.error
        assert "unknown_action_xyz" in result.error

    def test_missing_action_defaults_to_detect_all(self, evaluator):
        """缺少 action 参数时应默认为 detect_all"""
        # Arrange - 不提供 action
        request = EvaluationSchema(
            id="test-008",
            type="risk",
            payload={
                "feature_complexity": 0.2,
                "core_alignment": 0.8
            }
        )
        
        # Act
        result = evaluator.evaluate(request)
        
        # Assert - 应执行 detect_all
        assert result.is_valid is True
        assert "overall_risk_level" in result.data
        assert "details" in result.data

    def test_invalid_metric_type_raises_error(self, evaluator):
        """无效的指标类型应抛出异常（验证输入验证）"""
        # Arrange - 提供字符串而非数值
        request = EvaluationSchema(
            id="test-009",
            type="risk",
            payload={
                "action": "feature_creep",
                "feature_complexity": "invalid",  # 字符串而非数值
                "core_alignment": None
            }
        )
        
        # Act & Assert - 应抛出 TypeError
        with pytest.raises(TypeError):
            result = evaluator.evaluate(request)


# ============================================================
# Part 3: 边界测试 - 边界值
# ============================================================
class TestRiskEvaluatorBoundaryCases:
    """边界测试 - 验证边界值处理"""

    @pytest.fixture
    def evaluator(self):
        return RiskEvaluator()

    def test_empty_payload_uses_defaults(self, evaluator):
        """空 payload 应使用默认值（可能产生高风险）"""
        # Arrange
        request = EvaluationSchema(
            id="test-010",
            type="risk",
            payload={}
        )
        
        # Act
        result = evaluator.evaluate(request)
        
        # Assert - 应成功执行
        assert result.is_valid is True
        assert "overall_risk_level" in result.data
        # 空payload使用默认值，某些风险可能为高风险
        # 例如：drift检测中 baseline_score=0, current_score=0，score_drift=0
        # 但其他风险可能因默认值导致高风险
        assert result.data["overall_risk_level"] in ("low", "medium", "high")

    def test_maximum_values_for_all_metrics(self, evaluator):
        """所有指标最大值场景"""
        # Arrange - 所有指标都设为最大值
        request = EvaluationSchema(
            id="test-011",
            type="risk",
            payload={
                "action": "detect_all",
                "feature_complexity": 1.0,
                "core_alignment": 0.0,
                "responsibility_blur": 1.0,
                "unresolved_warnings": 1000,
                "duplicate_code_ratio": 1.0,
                "pending_refactoring": 100,
                "documentation_gap": 1.0,
                "external_dependencies": 20,
                "cyclic_dependencies": 1.0,
                "cross_layer_calls": 1.0,
                "overall_coverage": 0.0,
                "new_code_coverage": 0.0,
                "critical_path_coverage": 0.0,
                "test_pass_rate": 0.0,
                "baseline_score": 1.0,
                "current_score": 0.0,
                "format_changes": 20,
                "latency_increase": 200,
                "error_rate_change": 0.2
            }
        )
        
        # Act
        result = evaluator.evaluate(request)
        
        # Assert - 应检测到高风险
        assert result.is_valid is True
        assert result.data["overall_risk_level"] == "high"
        assert len(result.data["high_risks"]) > 0

    def test_threshold_boundary_for_high_risk(self, evaluator):
        """高风险阈值边界测试"""
        # Arrange - 确保风险评分刚好达到高风险阈值（0.7）
        # 公式: (1 - core_alignment) * 0.5 + feature_complexity * 0.3 + responsibility_blur * 0.2
        # 需要达到 0.7: (1 - 0.0) * 0.5 + 0.7 * 0.3 + 0.0 * 0.2 = 0.5 + 0.21 = 0.71
        request = EvaluationSchema(
            id="test-012",
            type="risk",
            payload={
                "action": "feature_creep",
                "feature_complexity": 0.7,  # 使总评分达到阈值
                "core_alignment": 0.0,      # 完全不对齐
                "responsibility_blur": 0.0
            }
        )
        
        # Act
        result = evaluator.evaluate(request)
        
        # Assert - 应为高风险
        assert result.is_valid is True
        # 风险评分: 0.5 + 0.21 = 0.71 >= 0.7
        assert result.data["risk_score"] >= 0.7
        assert result.data["risk_level"] == "high"

    def test_threshold_boundary_for_medium_risk(self, evaluator):
        """中风险阈值边界测试"""
        # Arrange - 刚好达到中风险阈值
        threshold = RiskEvaluator.RISK_THRESHOLDS["feature_creep"]
        request = EvaluationSchema(
            id="test-013",
            type="risk",
            payload={
                "action": "feature_creep",
                "feature_complexity": 0.0,
                "core_alignment": 1.0 - threshold * 0.5 * 2,  # 使 risk_score ≈ threshold * 0.5
                "responsibility_blur": 0.0
            }
        )
        
        # Act
        result = evaluator.evaluate(request)
        
        # Assert - 应为中风险或低风险
        assert result.is_valid is True
        assert result.data["risk_level"] in ("medium", "low")

    def test_zero_values_for_all_metrics(self, evaluator):
        """所有指标为零值场景"""
        # Arrange
        request = EvaluationSchema(
            id="test-014",
            type="risk",
            payload={
                "action": "tech_debt",
                "unresolved_warnings": 0,
                "duplicate_code_ratio": 0,
                "pending_refactoring": 0,
                "documentation_gap": 0
            }
        )
        
        # Act
        result = evaluator.evaluate(request)
        
        # Assert - 应为低风险
        assert result.is_valid is True
        assert result.data["risk_level"] == "low"
        assert result.data["risk_score"] == 0.0
        assert result.score == 1.0


# ============================================================
# Part 4: 风险等级测试 - 不同风险等级场景
# ============================================================
class TestRiskEvaluatorRiskLevels:
    """风险等级测试 - 验证风险等级判断逻辑"""

    @pytest.fixture
    def evaluator(self):
        return RiskEvaluator()

    def test_get_risk_level_high(self, evaluator):
        """_get_risk_level 应正确判断高风险"""
        # Arrange
        risk_score = 0.8
        threshold = 0.7
        
        # Act
        result = evaluator._get_risk_level(risk_score, threshold)
        
        # Assert
        assert result == "high"

    def test_get_risk_level_medium(self, evaluator):
        """_get_risk_level 应正确判断中风险"""
        # Arrange
        risk_score = 0.4
        threshold = 0.7
        
        # Act
        result = evaluator._get_risk_level(risk_score, threshold)
        
        # Assert
        assert result == "medium"

    def test_get_risk_level_low(self, evaluator):
        """_get_risk_level 应正确判断低风险"""
        # Arrange
        risk_score = 0.2
        threshold = 0.7
        
        # Act
        result = evaluator._get_risk_level(risk_score, threshold)
        
        # Assert
        assert result == "low"

    def test_detect_all_aggregates_multiple_high_risks(self, evaluator):
        """综合检测应正确聚合多个高风险"""
        # Arrange - 配置多个高风险指标
        request = EvaluationSchema(
            id="test-015",
            type="risk",
            payload={
                "action": "detect_all",
                "feature_complexity": 0.9,
                "core_alignment": 0.1,
                "unresolved_warnings": 100,
                "duplicate_code_ratio": 0.9,
                "overall_coverage": 0.2
            }
        )
        
        # Act
        result = evaluator.evaluate(request)
        
        # Assert - 应检测到多个高风险
        assert result.is_valid is True
        assert result.data["overall_risk_level"] == "high"
        assert len(result.data["high_risks"]) >= 1
        # 验证文本描述
        assert "高风险" in result.text

    def test_detect_all_aggregates_medium_risks(self, evaluator):
        """综合检测应正确聚合中风险"""
        # Arrange - 配置中风险指标
        request = EvaluationSchema(
            id="test-016",
            type="risk",
            payload={
                "action": "detect_all",
                "feature_complexity": 0.4,
                "core_alignment": 0.7,
                "unresolved_warnings": 30,
                "overall_coverage": 0.65
            }
        )
        
        # Act
        result = evaluator.evaluate(request)
        
        # Assert
        assert result.is_valid is True
        # 如果没有高风险，应有中风险
        if len(result.data["high_risks"]) == 0:
            assert result.data["overall_risk_level"] in ("medium", "low")


# ============================================================
# Part 5: 依赖测试 - 外部依赖和工厂注册
# ============================================================
class TestRiskEvaluatorDependencyHandling:
    """依赖测试 - 验证工厂注册和基类方法"""

    def test_evaluator_registered_in_factory(self):
        """评估器应正确注册到工厂"""
        # Arrange & Act
        from src.domain.evaluators import auto_discover
        from src.domain.evaluators.risk import RiskEvaluator as ImportedRiskEvaluator
        auto_discover(force=True)
        
        # Assert
        assert "risk" in EvaluatorFactory._registry
        # 验证注册的类是 RiskEvaluator 类型
        registered_class = EvaluatorFactory._registry["risk"]
        assert registered_class.__name__ == "RiskEvaluator"

    def test_factory_creates_evaluator_instance(self):
        """工厂应能创建评估器实例"""
        # Arrange
        from src.domain.evaluators import auto_discover
        auto_discover(force=True)
        
        # Act
        evaluator = EvaluatorFactory.get("risk")
        
        # Assert - 验证实例类型和方法
        assert evaluator is not None
        assert hasattr(evaluator, "evaluate")
        assert hasattr(evaluator, "_detect_all_risk")
        assert hasattr(evaluator, "RISK_THRESHOLDS")
        # 验证类名
        assert evaluator.__class__.__name__ == "RiskEvaluator"

    def test_evaluator_with_llm_client(self):
        """评估器应能接受 LLM 客户端（虽然当前不使用）"""
        # Arrange
        mock_client = MagicMock()
        mock_client.name = "mock_llm"
        
        # Act
        evaluator = RiskEvaluator(client=mock_client)
        
        # Assert
        assert evaluator.client is mock_client
        assert evaluator.client.name == "mock_llm"

    def test_evaluator_without_client_works(self):
        """评估器无需 LLM 客户端即可工作"""
        # Arrange
        evaluator = RiskEvaluator(client=None)
        request = EvaluationSchema(
            id="test-017",
            type="risk",
            payload={"action": "feature_creep"}
        )
        
        # Act
        result = evaluator.evaluate(request)
        
        # Assert - 应正常工作
        assert result.is_valid is True
        assert "risk_type" in result.data

    def test_get_payload_data_extracts_value(self):
        """get_payload_data 应正确提取 payload 数据"""
        # Arrange
        evaluator = RiskEvaluator()
        request = EvaluationSchema(
            id="test-018",
            type="risk",
            payload={"custom_key": "custom_value"}
        )
        
        # Act
        value = evaluator.get_payload_data(request, "custom_key", "default")
        
        # Assert
        assert value == "custom_value"

    def test_get_payload_data_returns_default(self):
        """get_payload_data 应在键不存在时返回默认值"""
        # Arrange
        evaluator = RiskEvaluator()
        request = EvaluationSchema(
            id="test-019",
            type="risk",
            payload={}
        )
        
        # Act
        value = evaluator.get_payload_data(request, "nonexistent_key", "default_value")
        
        # Assert
        assert value == "default_value"


# ============================================================
# Part 6: 业务逻辑验证测试
# ============================================================
class TestRiskEvaluatorBusinessLogic:
    """业务逻辑验证测试 - 验证风险评分计算逻辑"""

    @pytest.fixture
    def evaluator(self):
        return RiskEvaluator()

    def test_feature_creep_score_calculation(self, evaluator):
        """功能蔓延风险评分计算公式验证"""
        # Arrange
        feature_complexity = 0.5
        core_alignment = 0.6
        responsibility_blur = 0.4
        
        # 预期公式: (1 - core_alignment) * 0.5 + feature_complexity * 0.3 + responsibility_blur * 0.2
        expected_score = (1 - core_alignment) * 0.5 + feature_complexity * 0.3 + responsibility_blur * 0.2
        
        request = EvaluationSchema(
            id="test-020",
            type="risk",
            payload={
                "action": "feature_creep",
                "feature_complexity": feature_complexity,
                "core_alignment": core_alignment,
                "responsibility_blur": responsibility_blur
            }
        )
        
        # Act
        result = evaluator.evaluate(request)
        
        # Assert - 验证评分计算精度
        assert abs(result.data["risk_score"] - expected_score) < 0.001

    def test_tech_debt_score_with_capped_warnings(self, evaluator):
        """技术债务评分应对警告数进行上限约束"""
        # Arrange - 超大警告数
        request = EvaluationSchema(
            id="test-021",
            type="risk",
            payload={
                "action": "tech_debt",
                "unresolved_warnings": 500,  # 超过100，应被限制为1.0
                "duplicate_code_ratio": 0.8,  # 高重复率
                "pending_refactoring": 20,    # 超过10，应被限制为1.0
                "documentation_gap": 0.8      # 高文档缺失
            }
        )
        
        # Act
        result = evaluator.evaluate(request)
        
        # Assert - 验证评分不超过1.0
        assert result.data["risk_score"] <= 1.0
        # min(500/100, 1) * 0.3 = 0.3
        # 0.8 * 0.3 = 0.24
        # min(20/10, 1) * 0.2 = 0.2
        # 0.8 * 0.2 = 0.16
        # 总计 0.3 + 0.24 + 0.2 + 0.16 = 0.9
        expected_score = 0.9
        assert abs(result.data["risk_score"] - expected_score) < 0.01

    def test_coupling_score_with_capped_dependencies(self, evaluator):
        """耦合评分应对外部依赖数进行上限约束"""
        # Arrange - 超大外部依赖数
        request = EvaluationSchema(
            id="test-022",
            type="risk",
            payload={
                "action": "coupling",
                "external_dependencies": 50,  # 超过10，应被限制
                "cyclic_dependencies": 0.5,
                "cross_layer_calls": 0.5
            }
        )
        
        # Act
        result = evaluator.evaluate(request)
        
        # Assert - 验证评分不超过1.0
        assert result.data["risk_score"] <= 1.0
        # min(50/10, 1) * 0.5 = 0.5
        # 0.5 * 0.3 + 0.5 * 0.2 = 0.25
        # 总计 0.5 + 0.25 = 0.75
        assert abs(result.data["risk_score"] - 0.75) < 0.01

    def test_test_coverage_score_calculation(self, evaluator):
        """测试覆盖风险评分计算公式验证"""
        # Arrange
        overall_coverage = 0.7
        new_code_coverage = 0.6
        critical_path_coverage = 0.5
        test_pass_rate = 0.9
        
        threshold = 0.8
        # 预期公式:
        # max(0, threshold - overall) * 0.25 + max(0, threshold - new) * 0.35
        # + max(0, threshold - critical) * 0.25 + (1 - pass_rate) * 0.15
        expected_score = (
            max(0, threshold - overall_coverage) * 0.25
            + max(0, threshold - new_code_coverage) * 0.35
            + max(0, threshold - critical_path_coverage) * 0.25
            + (1 - test_pass_rate) * 0.15
        )
        
        request = EvaluationSchema(
            id="test-023",
            type="risk",
            payload={
                "action": "test_coverage",
                "overall_coverage": overall_coverage,
                "new_code_coverage": new_code_coverage,
                "critical_path_coverage": critical_path_coverage,
                "test_pass_rate": test_pass_rate
            }
        )
        
        # Act
        result = evaluator.evaluate(request)
        
        # Assert
        assert abs(result.data["risk_score"] - expected_score) < 0.001

    def test_drift_score_calculation(self, evaluator):
        """漂移风险评分计算公式验证"""
        # Arrange
        baseline_score = 0.8
        current_score = 0.6
        format_changes = 5
        latency_increase = 30
        error_rate_change = 0.05
        
        score_drift = abs(baseline_score - current_score)
        expected_score = (
            score_drift * 0.4
            + min(format_changes / 10, 1) * 0.25
            + min(latency_increase / 100, 1) * 0.2
            + min(error_rate_change / 0.1, 1) * 0.15
        )
        
        request = EvaluationSchema(
            id="test-024",
            type="risk",
            payload={
                "action": "drift",
                "baseline_score": baseline_score,
                "current_score": current_score,
                "format_changes": format_changes,
                "latency_increase": latency_increase,
                "error_rate_change": error_rate_change
            }
        )
        
        # Act
        result = evaluator.evaluate(request)
        
        # Assert
        assert abs(result.data["risk_score"] - expected_score) < 0.001
        assert result.data["metrics"]["score_drift"] == score_drift


# ============================================================
# Part 7: 建议文本验证测试
# ============================================================
class TestRiskEvaluatorSuggestions:
    """建议文本验证测试 - 验证风险建议文本"""

    @pytest.fixture
    def evaluator(self):
        return RiskEvaluator()

    def test_high_risk_includes_suggestion(self, evaluator):
        """高风险应包含改进建议"""
        # Arrange
        request = EvaluationSchema(
            id="test-025",
            type="risk",
            payload={
                "action": "feature_creep",
                "feature_complexity": 0.9,
                "core_alignment": 0.1
            }
        )
        
        # Act
        result = evaluator.evaluate(request)
        
        # Assert
        assert result.is_valid is True
        assert result.data["risk_level"] == "high"
        assert "suggestion" in result.data
        assert len(result.data["suggestion"]) > 0
        assert "建议" in result.data["suggestion"]

    def test_low_risk_shows_positive_message(self, evaluator):
        """低风险应显示正面消息"""
        # Arrange
        request = EvaluationSchema(
            id="test-026",
            type="risk",
            payload={
                "action": "coupling",
                "external_dependencies": 2,
                "cyclic_dependencies": 0,
                "cross_layer_calls": 0
            }
        )
        
        # Act
        result = evaluator.evaluate(request)
        
        # Assert
        assert result.is_valid is True
        assert result.data["risk_level"] == "low"
        assert "良好" in result.data["suggestion"]


# ============================================================
# Part 8: 阈值常量验证测试
# ============================================================
class TestRiskEvaluatorThresholds:
    """阈值常量验证测试 - 验证风险阈值配置"""

    def test_thresholds_are_defined(self):
        """所有风险类型的阈值应已定义"""
        # Assert
        assert "feature_creep" in RiskEvaluator.RISK_THRESHOLDS
        assert "tech_debt" in RiskEvaluator.RISK_THRESHOLDS
        assert "coupling" in RiskEvaluator.RISK_THRESHOLDS
        assert "test_coverage" in RiskEvaluator.RISK_THRESHOLDS
        assert "drift" in RiskEvaluator.RISK_THRESHOLDS

    def test_thresholds_are_valid(self):
        """所有阈值应在合理范围内"""
        # Assert
        for risk_type, threshold in RiskEvaluator.RISK_THRESHOLDS.items():
            assert 0.0 <= threshold <= 1.0, f"{risk_type} 阈值 {threshold} 超出范围"
            assert threshold > 0, f"{risk_type} 阈值应为正值"

    def test_feature_creep_threshold(self):
        """功能蔓延阈值应为 0.7"""
        assert RiskEvaluator.RISK_THRESHOLDS["feature_creep"] == 0.7

    def test_tech_debt_threshold(self):
        """技术债务阈值应为 0.6"""
        assert RiskEvaluator.RISK_THRESHOLDS["tech_debt"] == 0.6

    def test_coupling_threshold(self):
        """耦合阈值应为 0.5"""
        assert RiskEvaluator.RISK_THRESHOLDS["coupling"] == 0.5

    def test_test_coverage_threshold(self):
        """测试覆盖率阈值应为 0.8"""
        assert RiskEvaluator.RISK_THRESHOLDS["test_coverage"] == 0.8

    def test_drift_threshold(self):
        """漂移阈值应为 0.2"""
        assert RiskEvaluator.RISK_THRESHOLDS["drift"] == 0.2