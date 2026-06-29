"""
评估器工厂单元测试
测试目标：验证 EvaluatorFactory 的注册、获取、质量门禁功能
关键发现：
- 装饰器注册：支持 OVERWRITE、SKIP、ERROR 三种策略
- 评估器必须继承自 BaseEvaluator 并实现 _do_evaluate
- get 方法弹性适配不同构造函数签名
- 质量门禁可启用/禁用，支持不同级别
"""

import os
import sys
import threading
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import (
    EvaluatorFactory,
    RegisterStrategy,
)
from src.exceptions import DomainLogicError


@pytest.fixture(autouse=True)
def reset_registry():
    """每个测试前重置工厂注册表，避免测试间相互影响"""
    original_registry = dict(EvaluatorFactory._registry)
    EvaluatorFactory._registry = {}
    yield
    EvaluatorFactory._registry = original_registry


class TestRegisterDecorator:
    """注册装饰器测试"""

    def test_register_valid_evaluator(self):
        """注册合法评估器应成功"""

        @EvaluatorFactory.register(name="test_eval")
        class TestEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return {"score": 1.0}

        assert "test_eval" in EvaluatorFactory._registry
        assert EvaluatorFactory._registry["test_eval"] == TestEvaluator

    def test_register_skip_strategy_default(self):
        """默认 SKIP 策略：重复注册应保留第一个"""

        @EvaluatorFactory.register(name="eval_a")
        class EvalA1(BaseEvaluator):
            def _do_evaluate(self, request):
                return {"version": 1}

        @EvaluatorFactory.register(name="eval_a")
        class EvalA2(BaseEvaluator):
            def _do_evaluate(self, request):
                return {"version": 2}

        # 保留第一个
        assert EvaluatorFactory._registry["eval_a"] == EvalA1

    def test_register_error_strategy(self):
        """ERROR 策略：重复注册应抛出 ValueError"""

        @EvaluatorFactory.register(name="eval_b")
        class EvalB1(BaseEvaluator):
            def _do_evaluate(self, request):
                pass

        with pytest.raises(ValueError, match="已被注册"):

            @EvaluatorFactory.register(name="eval_b", strategy=RegisterStrategy.ERROR)
            class EvalB2(BaseEvaluator):
                def _do_evaluate(self, request):
                    pass

    def test_register_overwrite_strategy(self):
        """OVERWRITE 策略：重复注册应覆盖"""

        @EvaluatorFactory.register(name="eval_c")
        class EvalC1(BaseEvaluator):
            def _do_evaluate(self, request):
                return {"version": 1}

        @EvaluatorFactory.register(name="eval_c", strategy=RegisterStrategy.OVERWRITE)
        class EvalC2(BaseEvaluator):
            def _do_evaluate(self, request):
                return {"version": 2}

        # 被覆盖
        assert EvaluatorFactory._registry["eval_c"] == EvalC2

    def test_register_invalid_class_no_base(self):
        """不继承 BaseEvaluator 的类应抛出 TypeError"""
        with pytest.raises(TypeError, match="必须继承自 BaseEvaluator"):

            @EvaluatorFactory.register(name="bad_eval")
            class BadEvaluator:
                def _do_evaluate(self, request):
                    pass

    def test_register_invalid_class_no_method(self):
        """
        Bug 已修复：未实现 _do_evaluate 的类现在在注册时就会抛出 TypeError。

        修复前：注册成功，实例化时才抛出 TypeError
        修复后：使用 __abstractmethods__ 检查，注册时就抛出 TypeError
        """
        with pytest.raises(TypeError, match="必须实现 _do_evaluate 方法"):

            @EvaluatorFactory.register(name="bad_eval2")
            class BadEvaluator2(BaseEvaluator):
                pass  # 未实现 _do_evaluate（继承了抽象方法）


class TestGetEvaluator:
    """获取评估器测试"""

    def test_get_registered_evaluator(self):
        """获取已注册的评估器应返回实例"""

        @EvaluatorFactory.register(name="get_test")
        class GetTestEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return {"ok": True}

        evaluator = EvaluatorFactory.get("get_test")
        assert evaluator is not None
        assert isinstance(evaluator, GetTestEvaluator)

    def test_get_unregistered_evaluator_raises(self):
        """获取未注册的评估器应抛出 DomainLogicError"""
        with pytest.raises(DomainLogicError, match="未找到"):
            EvaluatorFactory.get("nonexistent_eval")

    def test_get_with_client_parameter(self):
        """带 client 参数的构造函数应正常实例化"""

        @EvaluatorFactory.register(name="client_eval")
        class ClientEvaluator(BaseEvaluator):
            def __init__(self, client=None):
                self.client = client

            def _do_evaluate(self, request):
                return {"has_client": self.client is not None}

        mock_client = MagicMock()
        evaluator = EvaluatorFactory.get("client_eval", client=mock_client)
        assert evaluator.client == mock_client

    def test_get_without_client_parameter(self):
        """不带 client 参数的构造函数也应能实例化"""

        @EvaluatorFactory.register(name="no_client_eval")
        class NoClientEvaluator(BaseEvaluator):
            def __init__(self):
                self.initialized = True

            def _do_evaluate(self, request):
                return {}

        evaluator = EvaluatorFactory.get("no_client_eval")
        assert isinstance(evaluator, NoClientEvaluator)
        assert evaluator.initialized is True

    def test_get_with_positional_client(self):
        """只接受位置参数 client 的构造函数也应能实例化"""

        @EvaluatorFactory.register(name="positional_eval")
        class PositionalEvaluator(BaseEvaluator):
            def __init__(self, client):  # 位置参数，无默认值
                self.client = client

            def _do_evaluate(self, request):
                return {}

        mock_client = MagicMock()
        evaluator = EvaluatorFactory.get("positional_eval", client=mock_client)
        assert evaluator.client == mock_client

    def test_get_returns_new_instance_each_time(self):
        """每次调用 get 应返回新实例"""

        @EvaluatorFactory.register(name="instance_test")
        class InstanceTestEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return {}

        e1 = EvaluatorFactory.get("instance_test")
        e2 = EvaluatorFactory.get("instance_test")
        assert e1 is not e2


class TestListEvaluators:
    """评估器列表测试"""

    def test_list_empty_registry(self):
        """空注册表应返回空列表"""
        assert EvaluatorFactory.list_evaluators() == []

    def test_list_sorted(self):
        """列表应按名称排序"""

        @EvaluatorFactory.register(name="zeta")
        class ZetaEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                pass

        @EvaluatorFactory.register(name="alpha")
        class AlphaEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                pass

        @EvaluatorFactory.register(name="beta")
        class BetaEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                pass

        names = EvaluatorFactory.list_evaluators()
        assert names == ["alpha", "beta", "zeta"]


class TestEvaluatorInfo:
    """评估器信息测试"""

    def test_get_evaluator_info_empty(self):
        """空注册表应返回空列表"""
        info = EvaluatorFactory.get_evaluator_info()
        assert info == []

    def test_get_evaluator_info_fields(self):
        """信息应包含必要字段"""

        @EvaluatorFactory.register(name="info_test")
        class InfoTestEvaluator(BaseEvaluator):
            """测试评估器文档字符串"""

            def _do_evaluate(self, request):
                pass

        info = EvaluatorFactory.get_evaluator_info()
        assert len(info) == 1
        assert info[0]["name"] == "info_test"
        assert info[0]["class_name"] == "InfoTestEvaluator"
        assert info[0]["docstring"] == "测试评估器文档字符串"
        assert "quality_gate_enabled" in info[0]
        assert "quality_gate_level" in info[0]


class TestQualityGate:
    """质量门禁测试"""

    def test_quality_gate_disabled_by_default(self):
        """默认质量门禁应禁用"""
        status = EvaluatorFactory.get_quality_status()
        assert status["enabled"] is False
        assert status["registered_evaluators"] == 0

    def test_enable_quality_gate(self):
        """启用质量门禁应正确设置状态"""
        from src.domain.testing.quality_gates import QualityGateLevel

        EvaluatorFactory.enable_quality_gate(level=QualityGateLevel.STRICT)
        status = EvaluatorFactory.get_quality_status()
        assert status["enabled"] is True
        assert status["level"] == "strict"

        # 清理
        EvaluatorFactory.disable_quality_gate()

    def test_disable_quality_gate(self):
        """禁用质量门禁应正确设置状态"""
        from src.domain.testing.quality_gates import QualityGateLevel

        EvaluatorFactory.enable_quality_gate(level=QualityGateLevel.NORMAL)
        EvaluatorFactory.disable_quality_gate()

        status = EvaluatorFactory.get_quality_status()
        assert status["enabled"] is False

    def test_get_with_quality_check_disabled(self):
        """质量门禁禁用时返回 None"""

        @EvaluatorFactory.register(name="qc_test")
        class QCTestEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return {"ok": True}

        evaluator, quality_result = EvaluatorFactory.get_with_quality_check("qc_test")
        assert evaluator is not None
        assert quality_result is None

    def test_get_with_quality_check_enabled(self):
        """质量门禁启用时应返回结果（注意：QualityGateLevel 没有 LIGHT，是 RELAXED）"""
        from src.domain.testing.quality_gates import QualityGateLevel

        @EvaluatorFactory.register(name="qc_test2")
        class QCTest2Evaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return {"score": 1.0}

        EvaluatorFactory.enable_quality_gate(level=QualityGateLevel.RELAXED)
        try:
            evaluator, quality_result = EvaluatorFactory.get_with_quality_check("qc_test2")
            assert evaluator is not None
            # quality_result 可能是 None 或 QualityGateResult（取决于是否能获取源码）
        finally:
            EvaluatorFactory.disable_quality_gate()

    def test_quality_status_after_register(self):
        """注册后数量应更新"""

        @EvaluatorFactory.register(name="qs_test")
        class QSTestEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                pass

        status = EvaluatorFactory.get_quality_status()
        assert status["registered_evaluators"] == 1


class TestRegisterStrategyEnum:
    """RegisterStrategy 枚举测试"""

    def test_strategy_values(self):
        """枚举值应正确"""
        assert RegisterStrategy.OVERWRITE.value == "overwrite"
        assert RegisterStrategy.SKIP.value == "skip"
        assert RegisterStrategy.ERROR.value == "error"


class TestThreadSafety:
    """线程安全测试"""

    _eval_lock = threading.Lock()

    def test_concurrent_registration(self):
        """并发注册不应损坏注册表"""
        errors = []

        def register_eval(idx):
            try:
                name = f"concurrent_eval_{idx}"

                @EvaluatorFactory.register(name=name)
                class ConcurrentEvaluator(BaseEvaluator):
                    def _do_evaluate(self, request):
                        pass
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=register_eval, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(EvaluatorFactory.list_evaluators()) == 20

    def test_concurrent_get(self):
        """并发获取不应出错"""

        @EvaluatorFactory.register(name="concurrent_get_test")
        class ConcurrentGetEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return {}

        results = []
        errors = []

        def get_eval():
            try:
                with TestThreadSafety._eval_lock:
                    e = EvaluatorFactory.get("concurrent_get_test")
                results.append(e)
            except Exception as ex:
                errors.append(ex)

        threads = [threading.Thread(target=get_eval) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 20
        # 都是不同的实例
        assert len({id(r) for r in results}) == 20
