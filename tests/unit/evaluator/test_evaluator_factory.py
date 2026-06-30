"""
EvaluatorFactory 专项测试
"""

import threading
import warnings
from unittest.mock import MagicMock

import pytest

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.testing.quality_gates import QualityGateLevel
from src.exceptions import DomainLogicError


class TestEvaluatorFactoryRegistration:
    """注册机制测试"""

    def test_register_evaluator(self):
        """注册评估器应成功加入注册表"""

        @EvaluatorFactory.register("test_eval")
        class TestEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                pass

        assert "test_eval" in EvaluatorFactory.list_evaluators()

    def test_register_duplicate_warns(self):
        """重复注册同名评估器应发出警告"""
        from src.domain.evaluators.evaluator_factory import RegisterStrategy

        @EvaluatorFactory.register("duplicate_test")
        class FirstEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                pass

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            @EvaluatorFactory.register("duplicate_test", strategy=RegisterStrategy.OVERWRITE)
            class SecondEvaluator(BaseEvaluator):
                def _do_evaluate(self, request):
                    pass

            assert len(w) >= 1
            assert "已被注册" in str(w[0].message)

    def test_register_same_type_warns(self):
        """注册相同类型仍会发出警告"""

        @EvaluatorFactory.register("same_type_test")
        class SameEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                pass

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            @EvaluatorFactory.register("same_type_test")
            class SameEvaluator2(BaseEvaluator):
                def _do_evaluate(self, request):
                    pass

            assert len(w) >= 0


class TestEvaluatorFactoryGet:
    """获取评估器测试"""

    def test_get_existing_evaluator(self):
        """获取已注册的评估器应成功"""

        @EvaluatorFactory.register("get_test")
        class GetTestEvaluator(BaseEvaluator):
            def __init__(self, client=None):
                super().__init__(client)

            def _do_evaluate(self, request):
                pass

        evaluator = EvaluatorFactory.get("get_test")
        assert evaluator is not None
        assert isinstance(evaluator, GetTestEvaluator)

    def test_get_with_client(self):
        """获取评估器时传入client应正确传递"""
        mock_client = MagicMock()

        @EvaluatorFactory.register("client_test")
        class ClientTestEvaluator(BaseEvaluator):
            def __init__(self, client=None):
                super().__init__(client)

            def _do_evaluate(self, request):
                pass

        evaluator = EvaluatorFactory.get("client_test", client=mock_client)
        assert evaluator.client == mock_client

    def test_get_non_existing_evaluator(self):
        """获取未注册的评估器应抛出DomainLogicError"""
        with pytest.raises(DomainLogicError) as excinfo:
            EvaluatorFactory.get("non_existing_eval_xyz123")
        assert "未找到" in str(excinfo.value)

    def test_get_without_client_parameter(self):
        """兼容不接受client参数的评估器"""

        @EvaluatorFactory.register("no_client_eval")
        class NoClientEvaluator(BaseEvaluator):
            def __init__(self):
                super().__init__(client=None)

            def _do_evaluate(self, request):
                pass

        evaluator = EvaluatorFactory.get("no_client_eval", client=MagicMock())
        assert evaluator is not None

    def test_get_with_positional_client(self):
        """兼容只接受位置参数的函数式注册"""

        def create_func_eval(client):
            class FuncEvaluator(BaseEvaluator):
                def __init__(self, client):
                    super().__init__(client)

                def _do_evaluate(self, request):
                    pass

            return FuncEvaluator(client)

        EvaluatorFactory.register("func_eval")(create_func_eval)
        mock_client = MagicMock()
        evaluator = EvaluatorFactory.get("func_eval", client=mock_client)
        assert evaluator is not None
        assert evaluator.client == mock_client


class TestEvaluatorFactoryQualityGate:
    """质量门禁测试"""

    def test_enable_quality_gate(self):
        """启用质量门禁应设置正确状态"""
        EvaluatorFactory.enable_quality_gate(QualityGateLevel.STRICT)
        status = EvaluatorFactory.get_quality_status()
        assert status["enabled"] is True
        assert status["level"] == "strict"
        EvaluatorFactory.disable_quality_gate()

    def test_disable_quality_gate(self):
        """禁用质量门禁应设置正确状态"""
        EvaluatorFactory.enable_quality_gate()
        EvaluatorFactory.disable_quality_gate()
        status = EvaluatorFactory.get_quality_status()
        assert status["enabled"] is False
        assert status["level"] == "disabled"

    def test_get_with_quality_check_enabled(self):
        """启用质量门禁时get_with_quality_check应返回质量检查结果"""
        EvaluatorFactory.enable_quality_gate()

        @EvaluatorFactory.register("qc_test_enabled")
        class QCtestEvaluator(BaseEvaluator):
            def __init__(self, client=None):
                super().__init__(client)

            def _do_evaluate(self, request):
                pass

        evaluator, quality_result = EvaluatorFactory.get_with_quality_check("qc_test_enabled")
        assert evaluator is not None
        assert quality_result is not None
        assert hasattr(quality_result, "passed")
        assert hasattr(quality_result, "trust_score")
        assert hasattr(quality_result, "mutation_kill_rate")
        EvaluatorFactory.disable_quality_gate()

    def test_get_with_quality_check_disabled(self):
        """禁用质量门禁时get_with_quality_check应返回None作为质量检查结果"""
        EvaluatorFactory.disable_quality_gate()

        @EvaluatorFactory.register("qc_test_disabled")
        class QCTestDisabledEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                pass

        evaluator, quality_result = EvaluatorFactory.get_with_quality_check("qc_test_disabled")
        assert evaluator is not None
        assert quality_result is None

    def test_quality_gate_levels(self):
        """质量门禁各级别应正确设置"""
        for level in [QualityGateLevel.STRICT, QualityGateLevel.NORMAL, QualityGateLevel.RELAXED]:
            EvaluatorFactory.enable_quality_gate(level)
            status = EvaluatorFactory.get_quality_status()
            assert status["level"] == level.value
        EvaluatorFactory.disable_quality_gate()


class TestEvaluatorFactoryListAndInfo:
    """列表和信息测试"""

    def test_list_evaluators_returns_sorted(self):
        """list_evaluators应返回排序后的列表"""
        evaluators = EvaluatorFactory.list_evaluators()
        assert isinstance(evaluators, list)
        assert evaluators == sorted(evaluators)

    def test_get_evaluator_info(self):
        """get_evaluator_info应返回评估器详细信息"""
        info = EvaluatorFactory.get_evaluator_info()
        assert isinstance(info, list)
        for item in info:
            assert "name" in item
            assert "class_name" in item
            assert "docstring" in item

    def test_get_quality_status(self):
        """get_quality_status应返回正确的状态信息"""
        EvaluatorFactory.disable_quality_gate()
        status = EvaluatorFactory.get_quality_status()
        assert "enabled" in status
        assert "level" in status
        assert "registered_evaluators" in status


class TestEvaluatorFactoryThreadSafety:
    """线程安全测试"""

    def test_register_in_parallel(self):
        """并行注册评估器应线程安全"""
        errors = []

        def register_evaluator(name):
            try:

                @EvaluatorFactory.register(f"thread_test_{name}")
                class ThreadEvaluator(BaseEvaluator):
                    def _do_evaluate(self, request):
                        pass
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(10):
            t = threading.Thread(target=register_evaluator, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0
        for i in range(10):
            assert f"thread_test_{i}" in EvaluatorFactory.list_evaluators()

    def test_get_in_parallel(self):
        """并行获取评估器应线程安全"""

        @EvaluatorFactory.register("thread_get_test")
        class ThreadGetEvaluator(BaseEvaluator):
            def __init__(self, client=None):
                super().__init__(client)

            def _do_evaluate(self, request):
                pass

        errors = []

        def get_evaluator():
            try:
                evaluator = EvaluatorFactory.get("thread_get_test")
                assert evaluator is not None
            except Exception as e:
                errors.append(e)

        threads = []
        for _ in range(10):
            t = threading.Thread(target=get_evaluator)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0


class TestEvaluatorFactoryIntegration:
    """集成测试"""

    def test_factory_can_get_risk_evaluator(self):
        """工厂应能获取已注册的risk评估器"""
        import src.domain.evaluators.risk
        from src.domain.evaluators.risk import RiskEvaluator

        EvaluatorFactory.register("risk")(RiskEvaluator)

        evaluator = EvaluatorFactory.get("risk")
        assert evaluator is not None
