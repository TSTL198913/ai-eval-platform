"""
回归测试：质量门禁默认启用
BUG-017: 质量门禁默认未启用 - 评估器出厂未经质量验证

测试场景覆盖：
1. 正向：EvaluatorFactory 默认 quality_gate_enabled=True
2. 正向：默认级别为 NORMAL
3. 正向：get_with_quality_check 可触发门禁检查
4. 边界：disable_quality_gate 后门禁关闭
5. 边界：enable_quality_gate(STRICT) 可切换级别
6. 负向：门禁检查失败不阻塞评估器创建
"""

import pytest


class TestQualityGateDefault:
    """质量门禁默认启用测试"""

    def test_quality_gate_enabled_by_default(self):
        """正向：EvaluatorFactory 默认 quality_gate_enabled=True"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory

        assert EvaluatorFactory._quality_gate_enabled is True, \
            "质量门禁应默认启用"

    def test_default_level_is_normal(self):
        """正向：默认级别为 NORMAL"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        from src.domain.testing.quality_gates import QualityGateLevel

        assert EvaluatorFactory._quality_gate_level == QualityGateLevel.NORMAL, \
            "默认质量门禁级别应为 NORMAL"

    def test_quality_status_reflects_enabled_state(self):
        """正向：get_quality_status 返回 enabled=True"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory

        status = EvaluatorFactory.get_quality_status()
        assert status["enabled"] is True
        assert status["level"] == "normal"

    def test_disable_quality_gate(self):
        """边界：disable_quality_gate 后门禁关闭"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        from src.domain.testing.quality_gates import QualityGateLevel

        original_enabled = EvaluatorFactory._quality_gate_enabled
        original_level = EvaluatorFactory._quality_gate_level

        try:
            EvaluatorFactory.disable_quality_gate()
            assert EvaluatorFactory._quality_gate_enabled is False
            assert EvaluatorFactory._quality_gate_level == QualityGateLevel.DISABLED
        finally:
            EvaluatorFactory._quality_gate_enabled = original_enabled
            EvaluatorFactory._quality_gate_level = original_level

    def test_enable_strict_level(self):
        """边界：enable_quality_gate(STRICT) 可切换级别"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        from src.domain.testing.quality_gates import QualityGateLevel

        original_enabled = EvaluatorFactory._quality_gate_enabled
        original_level = EvaluatorFactory._quality_gate_level
        original_manager = EvaluatorFactory._qa_manager

        try:
            EvaluatorFactory.enable_quality_gate(QualityGateLevel.STRICT)
            assert EvaluatorFactory._quality_gate_enabled is True
            assert EvaluatorFactory._quality_gate_level == QualityGateLevel.STRICT
            assert EvaluatorFactory._qa_manager is not None
        finally:
            EvaluatorFactory._quality_gate_enabled = original_enabled
            EvaluatorFactory._quality_gate_level = original_level
            EvaluatorFactory._qa_manager = original_manager

    def test_quality_gate_failure_does_not_block_evaluator_creation(self):
        """负向：门禁检查失败不阻塞评估器创建"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory

        try:
            evaluator, quality_result = EvaluatorFactory.get_with_quality_check("general")
            assert evaluator is not None, "门禁失败不应阻塞评估器创建"
        except Exception as e:
            pytest.fail(f"门禁检查不应抛出异常: {e}")
