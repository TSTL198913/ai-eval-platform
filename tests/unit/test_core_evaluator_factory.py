"""
系统核心功能测试 - EvaluatorFactory
测试目标：验证评估器工厂的注册、获取、对象池、质量门禁等核心机制
覆盖场景：正常测试、边界值测试、异常测试、空值测试、参数组合测试
"""

import pytest

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import (
    EvaluatorFactory,
    RegisterStrategy,
)
from src.domain.testing.quality_gates import QualityGateLevel
from src.exceptions import DomainLogicError
from src.schemas.evaluation import DomainResponse, EvaluationSchema


class TestEvaluatorFactoryRegistration:
    """评估器注册测试"""

    def test_register_evaluator_success(self):
        """正常注册评估器应成功"""
        @EvaluatorFactory.register("test_success_eval")
        class TestSuccessEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(is_valid=True, score=1.0)

        assert "test_success_eval" in EvaluatorFactory.list_evaluators()

    def test_register_evaluator_with_overwrite_strategy(self):
        """OVERWRITE策略应覆盖已注册的评估器"""
        @EvaluatorFactory.register("test_overwrite_eval")
        class OriginalEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(is_valid=True, score=0.5)

        @EvaluatorFactory.register("test_overwrite_eval", strategy=RegisterStrategy.OVERWRITE)
        class OverwriteEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(is_valid=True, score=1.0)

        evaluator = EvaluatorFactory.get("test_overwrite_eval")
        assert isinstance(evaluator, OverwriteEvaluator)

    def test_register_evaluator_with_error_strategy_raises(self):
        """ERROR策略应在重复注册时抛出异常"""
        @EvaluatorFactory.register("test_error_eval")
        class FirstEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(is_valid=True, score=1.0)

        with pytest.raises(ValueError, match="已被注册"):
            @EvaluatorFactory.register("test_error_eval", strategy=RegisterStrategy.ERROR)
            class SecondEvaluator(BaseEvaluator):
                def _do_evaluate(self, request):
                    return DomainResponse(is_valid=True, score=0.5)

    def test_register_evaluator_without_base_evaluator_raises(self):
        """注册非BaseEvaluator子类应抛出异常"""
        with pytest.raises(TypeError, match="必须继承自 BaseEvaluator"):
            @EvaluatorFactory.register("invalid_eval")
            class InvalidEvaluator:
                pass

    def test_register_evaluator_without_do_evaluate_raises(self):
        """注册未实现_do_evaluate的抽象类应抛出异常"""
        with pytest.raises(TypeError, match="必须实现 _do_evaluate"):
            @EvaluatorFactory.register("abstract_eval")
            class AbstractEvaluator(BaseEvaluator):
                pass

    def test_register_duplicate_name_skip_strategy(self):
        """SKIP策略应跳过重复注册"""
        @EvaluatorFactory.register("test_skip_eval")
        class FirstEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(is_valid=True, score=1.0)

        @EvaluatorFactory.register("test_skip_eval")
        class SecondEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(is_valid=True, score=0.5)

        evaluator = EvaluatorFactory.get("test_skip_eval")
        assert isinstance(evaluator, FirstEvaluator)


class TestEvaluatorFactoryGet:
    """评估器获取测试"""

    def test_get_existing_evaluator(self):
        """获取已注册的评估器应成功"""
        @EvaluatorFactory.register("test_get_eval")
        class TestGetEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(is_valid=True, score=0.8)

        evaluator = EvaluatorFactory.get("test_get_eval")
        assert isinstance(evaluator, TestGetEvaluator)

    def test_get_nonexistent_evaluator_raises(self):
        """获取未注册的评估器应抛出异常"""
        with pytest.raises(DomainLogicError, match="未找到"):
            EvaluatorFactory.get("nonexistent_eval")

    def test_get_evaluator_with_client(self):
        """获取评估器时传递客户端应成功"""
        @EvaluatorFactory.register("test_client_eval")
        class TestClientEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(is_valid=True, score=0.9)

        mock_client = object()
        evaluator = EvaluatorFactory.get("test_client_eval", client=mock_client)
        assert evaluator.client == mock_client

    def test_get_evaluator_without_pool(self):
        """禁用对象池时应每次创建新实例"""
        EvaluatorFactory.disable_pool()
        @EvaluatorFactory.register("test_no_pool_eval")
        class TestNoPoolEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(is_valid=True, score=0.7)

        evaluator1 = EvaluatorFactory.get("test_no_pool_eval")
        evaluator2 = EvaluatorFactory.get("test_no_pool_eval")
        assert evaluator1 is not evaluator2
        EvaluatorFactory.enable_pool()


class TestEvaluatorFactoryPool:
    """对象池测试"""

    def test_pool_reuse_evaluators(self):
        """对象池应复用评估器实例"""
        EvaluatorFactory.set_pool_size(5)
        @EvaluatorFactory.register("test_pool_eval")
        class TestPoolEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(is_valid=True, score=0.6)

        evaluator1 = EvaluatorFactory.get("test_pool_eval")
        EvaluatorFactory.release("test_pool_eval", evaluator1)
        evaluator2 = EvaluatorFactory.get("test_pool_eval")
        assert evaluator1 is evaluator2

    def test_pool_create_new_when_empty(self):
        """对象池为空时应创建新实例"""
        EvaluatorFactory.disable_pool()
        EvaluatorFactory.enable_pool()
        @EvaluatorFactory.register("test_pool_empty_eval")
        class TestPoolEmptyEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(is_valid=True, score=0.5)

        evaluator = EvaluatorFactory.get("test_pool_empty_eval")
        assert isinstance(evaluator, TestPoolEmptyEvaluator)

    def test_pool_release_when_disabled(self):
        """禁用对象池时release应无效果"""
        EvaluatorFactory.disable_pool()
        @EvaluatorFactory.register("test_pool_disabled_eval")
        class TestPoolDisabledEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(is_valid=True, score=0.4)

        evaluator = EvaluatorFactory.get("test_pool_disabled_eval")
        EvaluatorFactory.release("test_pool_disabled_eval", evaluator)
        evaluator2 = EvaluatorFactory.get("test_pool_disabled_eval")
        assert evaluator is not evaluator2
        EvaluatorFactory.enable_pool()


class TestEvaluatorFactoryQualityGate:
    """质量门禁测试"""

    def test_enable_quality_gate(self):
        """启用质量门禁应成功"""
        EvaluatorFactory.enable_quality_gate(QualityGateLevel.STRICT)
        status = EvaluatorFactory.get_quality_status()
        assert status["enabled"] is True
        assert status["level"] == "strict"
        EvaluatorFactory.disable_quality_gate()

    def test_disable_quality_gate(self):
        """禁用质量门禁应成功"""
        EvaluatorFactory.enable_quality_gate()
        EvaluatorFactory.disable_quality_gate()
        status = EvaluatorFactory.get_quality_status()
        assert status["enabled"] is False
        assert status["level"] == "disabled"

    def test_get_with_quality_check(self):
        """获取评估器并执行质量检查"""
        EvaluatorFactory.disable_quality_gate()
        @EvaluatorFactory.register("test_quality_eval")
        class TestQualityEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(is_valid=True, score=0.8)

        evaluator, quality_result = EvaluatorFactory.get_with_quality_check("test_quality_eval")
        assert isinstance(evaluator, TestQualityEvaluator)
        assert quality_result is None


class TestEvaluatorFactoryInfo:
    """评估器信息测试"""

    def test_list_evaluators(self):
        """列出所有已注册的评估器"""
        evaluators = EvaluatorFactory.list_evaluators()
        assert isinstance(evaluators, list)
        assert len(evaluators) > 0

    def test_get_evaluator_info(self):
        """获取评估器详细信息"""
        info = EvaluatorFactory.get_evaluator_info()
        assert isinstance(info, list)
        assert len(info) > 0
        for item in info:
            assert "name" in item
            assert "class_name" in item

    def test_get_quality_status(self):
        """获取质量门禁状态"""
        status = EvaluatorFactory.get_quality_status()
        assert "enabled" in status
        assert "level" in status
        assert "registered_evaluators" in status
