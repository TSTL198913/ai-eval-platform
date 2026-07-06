"""回归测试 - BUG-001 至 BUG-012

覆盖 data/failures_database.json 中记录的12个BUG的回归测试。
每个测试类对应一个BUG，确保修复后不再复发。

测试设计原则：
1. 显式引用BUG ID，便于追溯
2. 强断言验证业务逻辑（非仅status检查）
3. 覆盖正向、负向、边界场景
4. 不依赖测试执行顺序
"""

import os
import sys
import time
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.schemas.evaluation import (
    DomainResponse,
    EvaluationSchema,
    EvaluatorStatus,
)


# ============================================================================
# BUG-001: FineTunedEvaluator 无法实例化 - 抽象方法 _do_evaluate 未实现
# 修复：将 evaluate 方法重命名为 _do_evaluate
# 风险：若再次重写 evaluate() 而非 _do_evaluate()，将绕过熔断器和降级机制
# ============================================================================
class TestBUG001FineTunedEvaluatorDoEvaluate:
    """BUG-001 回归测试：FineTunedEvaluator 必须实现 _do_evaluate 而非重写 evaluate"""

    def test_evaluator_can_be_instantiated(self):
        """FineTunedEvaluator 应可被实例化（不触发 TypeError）"""
        from src.domain.fine_tuned_evaluator import FineTunedEvaluator

        evaluator = FineTunedEvaluator(model_path=None)
        assert evaluator is not None

    def test_do_evaluate_method_exists(self):
        """FineTunedEvaluator 必须有 _do_evaluate 方法"""
        from src.domain.fine_tuned_evaluator import FineTunedEvaluator

        evaluator = FineTunedEvaluator(model_path=None)
        assert hasattr(evaluator, "_do_evaluate")
        assert callable(getattr(evaluator, "_do_evaluate"))

    def test_do_evaluate_returns_domain_response_for_valid_input(self):
        """_do_evaluate 在有效输入下应返回 DomainResponse（mock 路径）"""
        from src.domain.fine_tuned_evaluator import FineTunedEvaluator

        evaluator = FineTunedEvaluator(model_path=None)
        request = EvaluationSchema(
            id="bug001-valid",
            type="fine_tuned",
            payload={
                "user_input": "什么是人工智能？",
                "actual_output": "人工智能是计算机科学的分支",
                "dimensions": ["correctness"],
            },
        )
        result = evaluator._do_evaluate(request)
        assert isinstance(result, DomainResponse)
        assert result.evaluation_status == EvaluatorStatus.SUCCESS
        assert result.score is not None
        assert 0.0 <= result.score <= 1.0

    def test_do_evaluate_returns_error_for_empty_input(self):
        """_do_evaluate 在空输入下应返回 ERROR 状态"""
        from src.domain.fine_tuned_evaluator import FineTunedEvaluator

        evaluator = FineTunedEvaluator(model_path=None)
        request = EvaluationSchema(
            id="bug001-empty",
            type="fine_tuned",
            payload={"user_input": "", "actual_output": ""},
        )
        result = evaluator._do_evaluate(request)
        assert result.evaluation_status == EvaluatorStatus.ERROR
        assert result.error is not None
        assert "actual_output" in result.error or "user_input" in result.error

    def test_evaluate_uses_breaker_and_returns_response(self):
        """evaluate() 通过熔断器调用 _do_evaluate，应正常返回响应"""
        from src.domain.fine_tuned_evaluator import FineTunedEvaluator

        evaluator = FineTunedEvaluator(model_path=None)
        request = EvaluationSchema(
            id="bug001-breaker",
            type="fine_tuned",
            payload={
                "user_input": "测试问题",
                "actual_output": "测试答案",
                "dimensions": ["correctness"],
            },
        )
        result = evaluator.evaluate(request)
        assert isinstance(result, DomainResponse)
        # evaluate 通过熔断器后应在 data 中注入 trace_id
        assert result.data is not None
        assert "trace_id" in result.data


# ============================================================================
# BUG-002: SecurityMiddleware 中 logger 未定义
# 修复：添加 import logging 和 logger = logging.getLogger(__name__)
# 风险：若 logger 未定义，中间件在异常处理时会抛出 NameError，导致请求中断
# ============================================================================
class TestBUG002SecurityMiddlewareLogger:
    """BUG-002 回归测试：SecurityMiddleware 必须有可用的 logger"""

    def test_logger_module_attribute_exists(self):
        """src.api.security_middleware 模块应有 logger 属性"""
        from src.api import security_middleware

        assert hasattr(security_middleware, "logger")
        assert security_middleware.logger is not None
        assert security_middleware.logger.name == "src.api.security_middleware"

    def test_middleware_handles_invalid_json_without_name_error(self):
        """中间件处理无效 JSON 时不应抛出 NameError"""
        from src.api.security_middleware import SecurityMiddleware

        middleware = SecurityMiddleware(app=MagicMock())

        # 构造无效 JSON 请求
        async def receive():
            return {"type": "http.request", "body": b"invalid json {{{"}

        request_scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/v2/evaluate",
            "headers": [(b"content-type", b"application/json")],
        }

        # 应不抛出 NameError（logger 未定义）
        try:
            import asyncio
            asyncio.get_event_loop().run_until_complete(
                middleware(request_scope, receive, MagicMock())
            )
        except NameError as e:
            pytest.fail(f"BUG-002 复发：logger 未定义 - {e}")
        except Exception:
            # 其他异常可接受（如 mock 响应对象不完整）
            pass


# ============================================================================
# BUG-003: DriftEvaluator 空输入未返回错误状态
# 修复：修改测试断言使用 evaluation_status 替代废弃的 is_valid
# 风险：DriftEvaluator 设计为 require_input=False，需验证空 actual_output 返回 ERROR
# ============================================================================
class TestBUG003DriftEvaluatorEmptyInput:
    """BUG-003 回归测试：DriftDetectionEvaluator 空输入处理"""

    def test_empty_actual_output_returns_error(self):
        """空 actual_output 应返回 ERROR 状态"""
        from src.domain.evaluators.drift import DriftDetectionEvaluator

        evaluator = DriftDetectionEvaluator()
        request = EvaluationSchema(
            id="bug003-empty-actual",
            type="drift",
            payload={"user_input": "测试问题", "actual_output": ""},
        )
        result = evaluator.evaluate(request)
        assert result.evaluation_status == EvaluatorStatus.ERROR
        assert result.error is not None
        assert "actual_output" in (result.error or "")

    def test_valid_input_returns_success(self):
        """有效输入应返回非 ERROR 状态"""
        from src.domain.evaluators.drift import DriftDetectionEvaluator

        evaluator = DriftDetectionEvaluator()
        request = EvaluationSchema(
            id="bug003-valid",
            type="drift",
            payload={
                "user_input": "什么是机器学习？",
                "actual_output": "机器学习是让计算机从数据中学习的技术",
            },
        )
        result = evaluator.evaluate(request)
        assert result.evaluation_status != EvaluatorStatus.ERROR


# ============================================================================
# BUG-004: Engine 在线模式未调用 LLM 生成 actual_output
# 修复：移除 evaluate_mode == ONLINE 检查，改为基于数据可用性决定
# 风险：若恢复 ONLINE 模式判断，将导致无 actual_output 时不调用 LLM
# ============================================================================
class TestBUG004EngineOnlineModeInference:
    """BUG-004 回归测试：Engine 在数据缺失时应触发 LLM 推理"""

    def test_inference_triggered_when_actual_output_missing(self):
        """无 actual_output 时应调用 client.chat 生成输出"""
        from src.engine import EvaluationEngine
        from src.domain.evaluators.base import BaseEvaluator
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        from src.schemas.evaluation import EvaluationMode

        class MockBug004Evaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return self.create_success_response(text="ok", score=0.8)

        EvaluatorFactory.register("test_bug004")(MockBug004Evaluator)
        try:
            client = MagicMock()
            client.config = MagicMock()
            client.config.model_name = "test-model"
            client.chat.return_value = "generated output"

            engine = EvaluationEngine(client)
            request = EvaluationSchema(
                id="bug004-no-output",
                type="test_bug004",
                evaluate_mode=EvaluationMode.ONLINE,
                payload={"prompt": "测试问题", "expected_output": "期望答案"},
            )
            engine.run(request)

            # 核心断言：LLM 应被调用以生成 actual_output
            client.chat.assert_called_once()
            call_args = client.chat.call_args
            assert call_args is not None
        finally:
            if "test_bug004" in EvaluatorFactory._registry:
                del EvaluatorFactory._registry["test_bug004"]

    def test_inference_skipped_when_actual_output_provided(self):
        """已有 actual_output 时应跳过 LLM 推理"""
        from src.engine import EvaluationEngine
        from src.domain.evaluators.base import BaseEvaluator
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        from src.schemas.evaluation import EvaluationMode

        class MockBug004SkipEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return self.create_success_response(text="ok", score=0.9)

        EvaluatorFactory.register("test_bug004_skip")(MockBug004SkipEvaluator)
        try:
            client = MagicMock()
            client.config = MagicMock()
            client.config.model_name = "test-model"

            engine = EvaluationEngine(client)
            request = EvaluationSchema(
                id="bug004-has-output",
                type="test_bug004_skip",
                evaluate_mode=EvaluationMode.ONLINE,
                payload={
                    "actual_output": "已提供输出",
                    "expected_output": "期望答案",
                },
            )
            engine.run(request)

            # 核心断言：已有 actual_output 时不应调用 LLM
            client.chat.assert_not_called()
        finally:
            if "test_bug004_skip" in EvaluatorFactory._registry:
                del EvaluatorFactory._registry["test_bug004_skip"]


# ============================================================================
# BUG-005: RuntimeAgentEvaluator 缺少 get_tool_registry 方法
# 修复：添加 get_tool_registry 类方法
# 风险：若类方法被删除，外部调用将抛出 AttributeError
# ============================================================================
class TestBUG005RuntimeAgentGetToolRegistry:
    """BUG-005 回归测试：RuntimeAgentEvaluator.get_tool_registry 类方法"""

    def test_get_tool_registry_classmethod_exists(self):
        """get_tool_registry 应作为类方法存在"""
        from src.domain.evaluators.runtime_agent_evaluator import RuntimeAgentEvaluator

        assert hasattr(RuntimeAgentEvaluator, "get_tool_registry")
        assert callable(getattr(RuntimeAgentEvaluator, "get_tool_registry"))

    def test_get_tool_registry_returns_object(self):
        """get_tool_registry 应返回非 None 的工具注册中心"""
        from src.domain.evaluators.runtime_agent_evaluator import RuntimeAgentEvaluator

        registry = RuntimeAgentEvaluator.get_tool_registry()
        assert registry is not None

    def test_get_tool_registry_consistent_across_calls(self):
        """多次调用 get_tool_registry 应返回同一实例（类级共享）"""
        from src.domain.evaluators.runtime_agent_evaluator import RuntimeAgentEvaluator

        registry1 = RuntimeAgentEvaluator.get_tool_registry()
        registry2 = RuntimeAgentEvaluator.get_tool_registry()
        assert registry1 is registry2

    def test_instance_shares_class_registry(self):
        """实例的 _tool_registry 应与类方法返回的一致"""
        from src.domain.evaluators.runtime_agent_evaluator import RuntimeAgentEvaluator

        evaluator = RuntimeAgentEvaluator()
        class_registry = RuntimeAgentEvaluator.get_tool_registry()
        assert evaluator._tool_registry is class_registry


# ============================================================================
# BUG-006: adaptive_calibration 模块路径错误
# 修复：创建兼容性导入层 src/domain/adaptive_calibration.py
# 风险：若兼容层被删除，所有 from src.domain.adaptive_calibration import 将失败
# ============================================================================
class TestBUG006AdaptiveCalibrationCompatLayer:
    """BUG-006 回归测试：adaptive_calibration 兼容性导入层"""

    def test_module_importable(self):
        """src.domain.adaptive_calibration 应可被导入"""
        import src.domain.adaptive_calibration as mod
        assert mod is not None

    def test_key_symbols_exported(self):
        """兼容层应导出核心符号"""
        from src.domain.adaptive_calibration import (
            AdaptiveCalibrator,
            CalibrationAlert,
            CalibrationResult,
            CalibrationStats,
            CalibrationStatus,
            PreExecutionCheck,
            calibrator,
        )

        assert AdaptiveCalibrator is not None
        assert CalibrationResult is not None
        assert CalibrationStatus is not None
        assert calibrator is not None

    def test_calibrator_is_instance_of_adaptive_calibrator(self):
        """calibrator 应为 AdaptiveCalibrator 实例"""
        from src.domain.adaptive_calibration import AdaptiveCalibrator, calibrator

        assert isinstance(calibrator, AdaptiveCalibrator)

    def test_compatibility_layer_redirects_to_real_module(self):
        """兼容层导出的类应与实际模块一致"""
        from src.domain.adaptive_calibration import AdaptiveCalibrator as CompatClass
        from src.domain.calibration.adaptive_calibrator import AdaptiveCalibrator as RealClass

        assert CompatClass is RealClass


# ============================================================================
# BUG-007: sanitize_input 导入路径错误
# 修复：在 multi_agent_evaluator.py 添加 sanitize_input 兼容性导入
# 风险：若导入被移除，from src.domain.evaluators.multi_agent_evaluator import sanitize_input 将失败
# ============================================================================
class TestBUG007SanitizeInputImport:
    """BUG-007 回归测试：sanitize_input 兼容性导入"""

    def test_sanitize_input_importable_from_evaluator_module(self):
        """应可从 multi_agent_evaluator 模块导入 sanitize_input"""
        from src.domain.evaluators.multi_agent_evaluator import sanitize_input

        assert callable(sanitize_input)

    def test_sanitize_input_importable_from_state_manager(self):
        """应可从 multi_agent_state_manager 模块导入 sanitize_input"""
        from src.domain.evaluators.multi_agent_state_manager import sanitize_input

        assert callable(sanitize_input)

    def test_sanitize_input_same_function_from_both_paths(self):
        """两个导入路径应返回同一函数对象"""
        from src.domain.evaluators.multi_agent_evaluator import sanitize_input as f1
        from src.domain.evaluators.multi_agent_state_manager import sanitize_input as f2

        assert f1 is f2

    def test_sanitize_input_removes_html(self):
        """sanitize_input 应移除 HTML 标签"""
        from src.domain.evaluators.multi_agent_evaluator import sanitize_input

        result = sanitize_input("<script>alert('xss')</script>test")
        assert "<script>" not in result
        assert "alert" not in result
        assert "test" in result


# ============================================================================
# BUG-008: EvaluationCache 导入路径错误
# 修复：在 src/infra/cache/__init__.py 实现 EvaluationCache 类和 cached 装饰器
# 风险：若类被移除，所有 from src.infra.cache import EvaluationCache 将失败
# ============================================================================
class TestBUG008EvaluationCacheImport:
    """BUG-008 回归测试：EvaluationCache 类和 cached 装饰器"""

    def test_evaluation_cache_importable(self):
        """EvaluationCache 应可从 src.infra.cache 导入"""
        from src.infra.cache import EvaluationCache

        assert EvaluationCache is not None

    def test_cached_decorator_importable(self):
        """cached 装饰器应可从 src.infra.cache 导入"""
        from src.infra.cache import cached

        assert callable(cached)

    def test_evaluation_cache_set_and_get(self):
        """EvaluationCache 应支持 set/get 基本操作"""
        from src.infra.cache import EvaluationCache

        cache = EvaluationCache(ttl_seconds=60, max_size=10)
        cache.set("key1", {"score": 0.85})
        result = cache.get("key1")
        assert result == {"score": 0.85}

    def test_evaluation_cache_ttl_expiration(self):
        """EvaluationCache 应支持 TTL 过期"""
        from src.infra.cache import EvaluationCache

        cache = EvaluationCache(ttl_seconds=0.1, max_size=10)
        cache.set("key1", "value")
        time.sleep(0.15)
        result = cache.get("key1")
        assert result is None

    def test_evaluation_cache_lru_eviction(self):
        """EvaluationCache 应支持 LRU 淘汰"""
        from src.infra.cache import EvaluationCache

        cache = EvaluationCache(ttl_seconds=60, max_size=2)
        cache.set("k1", "v1")
        cache.set("k2", "v2")
        cache.set("k3", "v3")  # 应淘汰 k1
        assert cache.get("k1") is None
        assert cache.get("k2") == "v2"
        assert cache.get("k3") == "v3"

    def test_cached_decorator_caches_function_result(self):
        """cached 装饰器应缓存函数结果"""
        from src.infra.cache import cached

        call_count = 0

        @cached(ttl_seconds=60, max_size=10)
        def expensive_func(key):
            nonlocal call_count
            call_count += 1
            return f"value_{key}"

        r1 = expensive_func("k1")
        r2 = expensive_func("k1")
        assert r1 == r2 == "value_k1"
        assert call_count == 1  # 第二次应命中缓存


# ============================================================================
# BUG-009: FactualityEvaluator 测试使用已废弃的 is_valid 属性
# 修复：将所有 is_valid 断言替换为 evaluation_status
# 风险：is_valid 是计算字段，无法直接设置；使用它做业务判断会掩盖 ERROR 状态
# ============================================================================
class TestBUG009FactualityEvaluatorStatusMachine:
    """BUG-009 回归测试：FactualityEvaluator 必须使用 evaluation_status"""

    def test_success_response_uses_success_status(self):
        """成功评估应返回 evaluation_status=SUCCESS（使用 LLM mock）"""
        from src.domain.evaluators.factuality_evaluator import FactualityEvaluator

        # 使用 mock client 触发 LLM+规则融合路径
        client = MagicMock()
        client.chat.return_value = "0.85"

        evaluator = FactualityEvaluator(client=client)
        request = EvaluationSchema(
            id="bug009-success",
            type="factuality",
            payload={
                "user_input": "什么是人工智能？",
                "actual_output": "人工智能是计算机科学的分支",
                "expected_output": "人工智能是计算机科学的分支",
                "evidence": "人工智能是计算机科学的分支",
            },
        )
        result = evaluator.evaluate(request)
        # LLM 可解析分数时应返回 SUCCESS
        assert result.evaluation_status == EvaluatorStatus.SUCCESS
        assert result.score is not None
        assert 0.0 <= result.score <= 1.0
        # is_valid 应为 True（计算字段，由 SUCCESS 推导）
        assert result.is_valid is True

    def test_partial_response_when_llm_unavailable(self):
        """LLM 不可用时应返回 PARTIAL（降级评估），而非 ERROR"""
        from src.domain.evaluators.factuality_evaluator import FactualityEvaluator

        evaluator = FactualityEvaluator(client=None)
        request = EvaluationSchema(
            id="bug009-partial",
            type="factuality",
            payload={
                "user_input": "什么是人工智能？",
                "actual_output": "人工智能是计算机科学的分支",
                "expected_output": "人工智能是计算机科学的分支",
                "evidence": "人工智能是计算机科学的分支",
            },
        )
        result = evaluator.evaluate(request)
        # 降级评估应返回 PARTIAL，is_valid 仍为 True
        assert result.evaluation_status == EvaluatorStatus.PARTIAL
        assert result.is_valid is True

    def test_error_response_uses_error_status(self):
        """错误评估应返回 evaluation_status=ERROR"""
        from src.domain.evaluators.factuality_evaluator import FactualityEvaluator

        evaluator = FactualityEvaluator()
        request = EvaluationSchema(
            id="bug009-error",
            type="factuality",
            payload={"user_input": "", "actual_output": ""},
        )
        result = evaluator.evaluate(request)
        assert result.evaluation_status == EvaluatorStatus.ERROR
        # is_valid 应为 False（计算字段，由 ERROR 推导）
        assert result.is_valid is False


# ============================================================================
# BUG-010: 标准指标 API 返回 422 验证错误
# 修复：从黑名单移除 standard_metric；移除 nltk.download；区分业务/系统错误
# 风险：若 standard_metric 被重新加入黑名单，评估器将无法注册
# ============================================================================
class TestBUG010StandardMetricBlacklistAndApi:
    """BUG-010 回归测试：standard_metric 不应在黑名单中"""

    def test_standard_metric_not_in_blacklist(self):
        """standard_metric 不应在 _EVALUATOR_BLACKLIST 中"""
        from src.domain.evaluators import _EVALUATOR_BLACKLIST

        assert "standard_metric" not in _EVALUATOR_BLACKLIST

    def test_standard_metrics_module_no_network_download(self):
        """standard_metrics 模块导入时不应触发 nltk.download 网络调用"""
        import inspect

        from src.domain.metrics import standard_metrics

        source = inspect.getsource(standard_metrics)
        # 不应有实际的 nltk.download(...) 调用（字符串提示除外）
        lines = source.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            # 跳过注释和字符串提示
            if stripped.startswith("#"):
                continue
            if 'nltk.download' in stripped and not stripped.startswith('"'):
                # 允许在字符串中出现（如 warning 提示文本）
                if stripped.startswith('"') or stripped.startswith("'"):
                    continue
                # 检查是否是实际调用（非字符串字面量）
                if not any(quote in stripped for quote in ['"', "'"]):
                    pytest.fail(
                        f"BUG-010 复发：第{i+1}行存在 nltk.download 调用: {stripped}"
                    )

    def test_standard_metric_evaluator_importable(self):
        """standard_metric_evaluator 模块应可被导入"""
        from src.domain.evaluators import standard_metric_evaluator

        assert standard_metric_evaluator is not None


# ============================================================================
# BUG-011: 分布式锁评估失败 - expected_output 验证过严
# 修复：在测试 payload 中补充 expected_output 字段
# 风险：若评估器 require_expected=True，缺少 expected_output 将返回 ERROR
# ============================================================================
class TestBUG011DistributedIntegrationExpectedOutput:
    """BUG-011 回归测试：分布式集成测试 payload 必须包含 expected_output"""

    def test_evaluation_request_with_expected_output_succeeds(self):
        """包含 expected_output 的请求应能正常评估"""
        from src.domain.evaluators.general import GeneralEvaluator

        evaluator = GeneralEvaluator()
        request = EvaluationSchema(
            id="bug011-with-expected",
            type="general",
            payload={
                "user_input": "什么是机器学习？",
                "actual_output": "机器学习是让计算机从数据中学习的技术",
                "expected_output": "机器学习是AI的子领域",
            },
        )
        result = evaluator.evaluate(request)
        # 应不因缺少 expected_output 而返回 ERROR
        assert result.evaluation_status != EvaluatorStatus.ERROR or result.error is None \
            or "expected_output" not in (result.error or "")


# ============================================================================
# BUG-012: 熔断器状态变更跟踪次数不符预期
# 修复：_check_timeout_transition 不再调用 _transition_to，被动超时转换不计入 state_changes
# 风险：若被动转换计入 state_changes，将导致统计语义不一致
# ============================================================================
class TestBUG012CircuitBreakerStateChangesSemantics:
    """BUG-012 回归测试：熔断器状态变更计数语义"""

    def test_passive_timeout_transition_not_counted(self):
        """OPEN→HALF_OPEN 被动超时转换不应计入 state_changes"""
        from src.distributed.circuit_breaker import (
            CircuitBreaker,
            CircuitBreakerConfig,
            CircuitState,
        )

        config = CircuitBreakerConfig(
            failure_threshold=2,
            timeout_seconds=0.1,
        )
        cb = CircuitBreaker("bug012_passive", config=config, auto_load_redis=False)

        # 触发熔断：CLOSED → OPEN（1次显式转换）
        for _ in range(2):
            try:
                cb.call_sync(lambda: (_ for _ in ()).throw(ValueError("fail")))
            except ValueError:
                pass

        assert cb.is_open is True
        assert cb.stats.state_changes == 1  # 仅 CLOSED→OPEN

        # 等待超时：OPEN → HALF_OPEN（被动转换，不应计入）
        time.sleep(0.15)
        assert cb.is_half_open is True
        # 核心断言：state_changes 仍为 1，被动转换未计入
        assert cb.stats.state_changes == 1

    def test_explicit_transitions_are_counted(self):
        """显式转换（HALF_OPEN→CLOSED）应计入 state_changes"""
        from src.distributed.circuit_breaker import (
            CircuitBreaker,
            CircuitBreakerConfig,
        )

        config = CircuitBreakerConfig(
            failure_threshold=2,
            success_threshold=2,
            timeout_seconds=0.1,
        )
        cb = CircuitBreaker("bug012_explicit", config=config, auto_load_redis=False)

        # 触发熔断：CLOSED → OPEN（1次）
        for _ in range(2):
            try:
                cb.call_sync(lambda: (_ for _ in ()).throw(ValueError("fail")))
            except ValueError:
                pass

        # 等待超时进入 HALF_OPEN（被动，不计入）
        time.sleep(0.15)
        assert cb.is_half_open is True

        # 连续成功：HALF_OPEN → CLOSED（1次显式）
        cb.call_sync(lambda: "ok1")
        cb.call_sync(lambda: "ok2")

        assert cb.is_closed is True
        # 核心断言：2次显式转换（CLOSED→OPEN + HALF_OPEN→CLOSED）
        assert cb.stats.state_changes == 2

    def test_half_open_failure_reopen_is_counted(self):
        """HALF_OPEN→OPEN 显式转换应计入 state_changes"""
        from src.distributed.circuit_breaker import (
            CircuitBreaker,
            CircuitBreakerConfig,
        )

        config = CircuitBreakerConfig(
            failure_threshold=2,
            success_threshold=2,
            timeout_seconds=0.1,
        )
        cb = CircuitBreaker("bug012_reopen", config=config, auto_load_redis=False)

        # CLOSED → OPEN
        for _ in range(2):
            try:
                cb.call_sync(lambda: (_ for _ in ()).throw(ValueError("fail")))
            except ValueError:
                pass

        # 等待进入 HALF_OPEN
        time.sleep(0.15)
        assert cb.is_half_open is True

        # HALF_OPEN → OPEN（失败重开）
        try:
            cb.call_sync(lambda: (_ for _ in ()).throw(ValueError("fail again")))
        except ValueError:
            pass

        assert cb.is_open is True
        # 核心断言：2次显式转换（CLOSED→OPEN + HALF_OPEN→OPEN）
        assert cb.stats.state_changes == 2
