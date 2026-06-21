"""
质量门禁集成测试

验证质量保障模块与评估器工厂的集成功能
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.testing import (
    QUALITY_GATE_PRESETS,
    QualityAssuranceManager,
    QualityGateConfig,
    QualityGateLevel,
    QualityGateResult,
    TestType,
    blue_team_test,
    quality_gate,
    red_team_test,
)
from src.schemas.evaluation import DomainResponse, EvaluationSchema


class TestQualityGateIntegration:
    """质量门禁集成测试"""

    def test_quality_gate_level_thresholds(self):
        """测试质量门禁级别阈值"""
        # STRICT级别
        strict_config = QUALITY_GATE_PRESETS["production"]
        assert strict_config.level == QualityGateLevel.STRICT
        assert strict_config.min_trust_score == 0.9
        assert strict_config.min_mutation_kill_rate == 0.8

        # NORMAL级别
        normal_config = QUALITY_GATE_PRESETS["staging"]
        assert normal_config.level == QualityGateLevel.NORMAL
        assert normal_config.min_trust_score == 0.8
        assert normal_config.min_mutation_kill_rate == 0.6

        # RELAXED级别
        relaxed_config = QUALITY_GATE_PRESETS["development"]
        assert relaxed_config.level == QualityGateLevel.RELAXED
        assert relaxed_config.min_trust_score == 0.7
        assert relaxed_config.min_mutation_kill_rate == 0.5

    def test_quality_assurance_manager_singleton(self):
        """测试质量保障管理器单例模式"""
        manager1 = QualityAssuranceManager()
        manager2 = QualityAssuranceManager()

        assert manager1 is manager2

    def test_quality_gate_decorator(self):
        """测试质量门禁装饰器"""

        @quality_gate(level=QualityGateLevel.NORMAL)
        def sample_function(x):
            return x * 2

        # 调用函数应正常工作
        result = sample_function(5)
        assert result == 10

    def test_quality_gate_disabled(self):
        """测试禁用质量门禁"""

        @quality_gate(level=QualityGateLevel.DISABLED)
        def sample_function(x):
            return x * 2

        result = sample_function(5)
        assert result == 10

    def test_red_team_test_decorator(self):
        """测试Red Team测试装饰器"""

        @red_team_test(test_type=TestType.SECURITY, description="安全测试")
        def security_test():
            return True

        assert hasattr(security_test, "_red_team_test")
        assert security_test._test_type == TestType.SECURITY
        assert security_test._author == "human"

    def test_blue_team_test_decorator(self):
        """测试Blue Team测试装饰器"""

        @blue_team_test(test_type=TestType.FUNCTIONAL, description="功能测试")
        def functional_test():
            return True

        assert hasattr(functional_test, "_blue_team_test")
        assert functional_test._test_type == TestType.FUNCTIONAL
        assert functional_test._author == "ai"


class TestEvaluatorFactoryQualityIntegration:
    """评估器工厂质量门禁集成测试"""

    def test_enable_quality_gate(self):
        """测试启用质量门禁"""
        # 启用质量门禁
        EvaluatorFactory.enable_quality_gate(QualityGateLevel.STRICT)

        assert EvaluatorFactory._quality_gate_enabled is True
        assert EvaluatorFactory._quality_gate_level == QualityGateLevel.STRICT
        assert EvaluatorFactory._qa_manager is not None

    def test_disable_quality_gate(self):
        """测试禁用质量门禁"""
        # 先启用
        EvaluatorFactory.enable_quality_gate(QualityGateLevel.NORMAL)

        # 然后禁用
        EvaluatorFactory.disable_quality_gate()

        assert EvaluatorFactory._quality_gate_enabled is False
        assert EvaluatorFactory._quality_gate_level == QualityGateLevel.DISABLED

    def test_get_quality_status(self):
        """测试获取质量门禁状态"""
        EvaluatorFactory.enable_quality_gate(QualityGateLevel.NORMAL)

        status = EvaluatorFactory.get_quality_status()

        assert status["enabled"] is True
        assert status["level"] == "normal"
        assert "registered_evaluators" in status

    def test_get_evaluator_info_with_quality(self):
        """测试获取评估器信息包含质量门禁"""

        # 注册一个测试评估器
        @EvaluatorFactory.register("test_quality_evaluator")
        class TestQualityEvaluator(BaseEvaluator):
            """测试质量评估器"""

            def evaluate(self, request: EvaluationSchema) -> DomainResponse:
                return DomainResponse(is_valid=True, score=1.0)

        EvaluatorFactory.enable_quality_gate(QualityGateLevel.NORMAL)

        info = EvaluatorFactory.get_evaluator_info()

        # 查找测试评估器
        test_evaluator_info = None
        for item in info:
            if item["name"] == "test_quality_evaluator":
                test_evaluator_info = item
                break

        assert test_evaluator_info is not None
        assert test_evaluator_info["quality_gate_enabled"] is True
        assert test_evaluator_info["quality_gate_level"] == "normal"

    def test_get_with_quality_check(self):
        """测试带质量检查的评估器获取"""

        # 注册测试评估器
        @EvaluatorFactory.register("quality_check_test")
        class QualityCheckEvaluator(BaseEvaluator):
            """质量检查测试评估器"""

            def evaluate(self, request: EvaluationSchema) -> DomainResponse:
                return DomainResponse(is_valid=True, score=0.9)

        EvaluatorFactory.enable_quality_gate(QualityGateLevel.NORMAL)

        evaluator, quality_result = EvaluatorFactory.get_with_quality_check("quality_check_test")

        assert evaluator is not None
        assert quality_result is not None
        assert quality_result.passed is True


class TestQualityGateResult:
    """质量门禁结果测试"""

    def test_quality_gate_result_creation(self):
        """测试质量门禁结果创建"""
        result = QualityGateResult(
            passed=True,
            trust_score=0.85,
            mutation_kill_rate=0.75,
            recommendations=["测试通过"],
        )

        assert result.passed is True
        assert result.trust_score == 0.85
        assert result.mutation_kill_rate == 0.75
        assert len(result.recommendations) == 1

    def test_quality_gate_result_to_dict(self):
        """测试质量门禁结果转换为字典"""
        result = QualityGateResult(
            passed=False,
            trust_score=0.6,
            mutation_kill_rate=0.5,
            recommendations=["信任分数过低", "变异杀死率不足"],
        )

        result_dict = result.to_dict()

        assert result_dict["passed"] is False
        assert result_dict["trust_score"] == 0.6
        assert result_dict["mutation_kill_rate"] == 0.5
        assert len(result_dict["recommendations"]) == 2


class TestDefenseInDepthWorkflow:
    """多层防御网完整工作流测试"""

    def test_complete_quality_workflow(self):
        """测试完整的质量验证工作流"""
        # 1. 配置质量门禁
        config = QualityGateConfig(
            level=QualityGateLevel.NORMAL,
            enable_red_blue=True,
            enable_mutation=False,  # 简化测试
            min_trust_score=0.8,
        )

        manager = QualityAssuranceManager(config=config)

        # 2. 定义测试目标函数
        def target_function(value: int) -> int:
            if value < 0:
                raise ValueError("负数输入")
            return value * 2

        # 3. 执行质量门禁检查
        result = manager.run_quality_gate(
            module_name="test_workflow",
            target_function=target_function,
            config=config,
        )

        # 4. 验证结果
        assert result is not None
        assert isinstance(result, QualityGateResult)

    def test_quality_gate_with_evaluator_factory(self):
        """测试评估器工厂与质量门禁的完整集成"""

        # 1. 注册评估器
        @EvaluatorFactory.register("workflow_test_evaluator")
        class WorkflowTestEvaluator(BaseEvaluator):
            """工作流测试评估器"""

            def evaluate(self, request: EvaluationSchema) -> DomainResponse:
                return DomainResponse(
                    is_valid=True,
                    score=0.95,
                    details={"workflow": "passed"},
                )

        # 2. 启用质量门禁
        EvaluatorFactory.enable_quality_gate(QualityGateLevel.NORMAL)

        # 3. 获取评估器（带质量检查）
        evaluator, quality_result = EvaluatorFactory.get_with_quality_check(
            "workflow_test_evaluator"
        )

        # 4. 执行评估
        request = EvaluationSchema(
            id="test_001",
            type="workflow_test_evaluator",
            payload={"user_input": "test"},
        )

        response = evaluator.evaluate(request)

        # 5. 验证结果
        assert response.is_valid is True
        assert response.score == 0.95
        assert quality_result.passed is True

        # 6. 检查质量状态
        status = EvaluatorFactory.get_quality_status()
        assert status["enabled"] is True


class TestQualityGatePresets:
    """质量门禁预设配置测试"""

    def test_production_preset(self):
        """测试生产环境预设"""
        preset = QUALITY_GATE_PRESETS["production"]

        assert preset.level == QualityGateLevel.STRICT
        assert preset.enable_red_blue is True
        assert preset.enable_mutation is True
        assert preset.min_trust_score >= 0.9
        assert preset.min_mutation_kill_rate >= 0.8

    def test_staging_preset(self):
        """测试预发布环境预设"""
        preset = QUALITY_GATE_PRESETS["staging"]

        assert preset.level == QualityGateLevel.NORMAL
        assert preset.enable_red_blue is True
        assert preset.enable_mutation is True

    def test_development_preset(self):
        """测试开发环境预设"""
        preset = QUALITY_GATE_PRESETS["development"]

        assert preset.level == QualityGateLevel.RELAXED
        assert preset.enable_red_blue is True
        assert preset.enable_mutation is False  # 开发环境可禁用变异测试

    def test_preset_comparison(self):
        """测试预设配置对比"""
        production = QUALITY_GATE_PRESETS["production"]
        staging = QUALITY_GATE_PRESETS["staging"]
        development = QUALITY_GATE_PRESETS["development"]

        # 生产环境要求最高
        assert production.min_trust_score > staging.min_trust_score
        assert staging.min_trust_score > development.min_trust_score

        # 变异测试要求
        assert production.min_mutation_kill_rate > staging.min_mutation_kill_rate
        assert staging.min_mutation_kill_rate > development.min_mutation_kill_rate
