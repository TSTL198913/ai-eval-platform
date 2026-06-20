"""
集成测试 - 真实业务场景全链路
重点：多组件协作、跨层数据流、故障恢复
"""

import os
import sys
import threading
import time
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.domain.evaluators import auto_discover
from src.domain.evaluators.evaluator_factory import EvaluatorFactory as EF


@pytest.fixture(autouse=True)
def reset_evaluators_each_test():
    """每个测试前重置 EvaluatorFactory 并重新触发自动发现"""
    EF._registry = {}
    auto_discover(force=True)
    yield


# ============================================================
# Part 1: 锁+幂等 - 防重复评测
# ============================================================
class TestLockAndIdempotencyIntegration:
    """锁 + 幂等：防止同一 case 被多次评测"""

    def test_lock_and_idempotency_combined(self, fake_redis):
        """真实场景：用户连点提交按钮 + 多 worker 并发抢任务"""
        from src.distributed.idempotency import IdempotencyChecker
        from src.distributed.lock import DistributedLock

        request_id = "case_001"
        idempotency = IdempotencyChecker(fake_redis)
        lock = DistributedLock(fake_redis, request_id, ttl_seconds=30)

        # 第一个 worker 获取锁
        assert lock.acquire().state.value == "acquired"

        # check() 单独调用不标记，语义上是 "检查" 而非 "登记"
        # 关键业务流：先 check 幂等
        assert idempotency.check(request_id) is True  # 未标记
        # 然后 mark_processing 登记
        assert idempotency.mark_processing(request_id) is True

        # 第二个 worker：幂等检查失败（已被标记），锁也失败
        lock2 = DistributedLock(fake_redis, request_id, ttl_seconds=30, retry_times=1)
        assert lock2.acquire().state.value == "not_acquired"
        # 幂等检查返回 False
        assert idempotency.check(request_id) is False

        # 业务方清理：释放锁 + 清除幂等
        lock.release()
        idempotency.clear(request_id)

        # 现在新请求可以处理
        assert idempotency.check(request_id) is True
        # 锁也可以重新获取
        lock3 = DistributedLock(fake_redis, request_id, ttl_seconds=30, retry_times=1)
        assert lock3.acquire().state.value == "acquired"


# ============================================================
# Part 2: 熔断+重试 - LLM 服务降级
# ============================================================
class TestCircuitBreakerAndRetryIntegration:
    """熔断器 + 限流：LLM 故障保护链路"""

    @pytest.mark.asyncio
    async def test_circuit_breaker_with_rate_limiter(self, fake_redis):
        """场景：连续失败后熔断，配合限流降级"""
        from src.distributed.circuit_breaker import (
            CircuitBreaker,
            CircuitBreakerConfig,
            CircuitState,
        )
        from src.distributed.rate_limiter import RateLimitConfig, TokenBucket

        cb = CircuitBreaker(
            "llm_svc", CircuitBreakerConfig(failure_threshold=2, timeout_seconds=60)
        )
        bucket = TokenBucket(
            fake_redis, "llm_user", RateLimitConfig(max_tokens=100, refill_rate=10)
        )

        # 触发 2 次失败，熔断器打开
        async def failing_call():
            raise ConnectionError("LLM down")

        for _ in range(2):
            with pytest.raises(ConnectionError):
                await cb.call(failing_call)

        assert cb.state == CircuitState.OPEN

        # 熔断器打开后，新请求被快速拒绝（不调用下游）
        with pytest.raises(Exception) as exc_info:
            await cb.call(failing_call)
        # 业务期望：快速失败，避免线程阻塞
        assert "OPEN" in str(exc_info.value) or "rejected" in str(exc_info.value).lower()

        # 限流器应仍可正常工作（独立服务）
        assert bucket.allow().allowed is True


# ============================================================
# Part 3: Engine 完整链路 - 端到端业务场景
# ============================================================
class TestEngineEndToEndIntegration:
    """Engine 端到端：从用户请求到结果"""

    def test_general_evaluator_with_expected_passes(self):
        """场景：QA 场景，LLM 输出与预期匹配"""
        from unittest.mock import MagicMock

        from src.domain.evaluators.base import BaseEvaluator
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        from src.engine import EvaluationEngine
        from src.schemas.evaluation import DomainResponse, EvaluationSchema, EvaluationStatus

        # 注册一个独立的评估器，避免依赖 'general' (可能已被其他测试污染)
        @EvaluatorFactory.register("qa_test_passes")
        class QAEvalPass(BaseEvaluator):
            def evaluate(self, request):
                expected = request.payload.get("expected_output", "")
                request.payload.get("user_input", "")
                # 模拟 LLM 输出包含预期
                return DomainResponse(
                    is_valid=True,
                    text=f"答案是: {expected}",
                    score=0.95,
                )

        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "qa-bot"

        engine = EvaluationEngine(client)
        request = EvaluationSchema(
            id="qa_001",
            type="qa_test_passes",
            payload={
                "user_input": "法国首都是哪里？",
                "expected_output": "巴黎",
            },
        )
        result = engine.run(request)
        assert result.status == EvaluationStatus.PASSED
        assert result.adapter_name == "QAEvalPass"
        assert result.model_name == "qa-bot"
        assert result.latency_ms > 0

    def test_general_evaluator_with_expected_fails(self):
        """场景：QA 场景，LLM 输出与预期不匹配"""
        from src.domain.evaluators.base import BaseEvaluator
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        from src.engine import EvaluationEngine
        from src.schemas.evaluation import DomainResponse, EvaluationSchema, EvaluationStatus

        @EvaluatorFactory.register("qa_test_fails")
        class QAEvalFail(BaseEvaluator):
            def evaluate(self, request):
                # 模拟相似度低
                return DomainResponse(
                    is_valid=False,
                    score=0.3,
                    text="错误答案",
                )

        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "qa-bot"

        engine = EvaluationEngine(client)
        request = EvaluationSchema(
            id="qa_002",
            type="qa_test_fails",
            payload={
                "user_input": "法国首都是哪里？",
                "expected_output": "巴黎",
            },
        )
        result = engine.run(request)
        # 业务上：相似度低，应判定为 FAILED
        assert result.status == EvaluationStatus.FAILED

    def test_engine_latency_for_100_requests(self):
        """场景：100 个连续评测请求（生产压测）"""
        from src.engine import EvaluationEngine
        from src.schemas.evaluation import EvaluationSchema

        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "perf-test"
        client.chat = MagicMock(return_value="ok")

        engine = EvaluationEngine(client)

        start = time.perf_counter()
        for i in range(100):
            request = EvaluationSchema(
                id=f"perf_{i:03d}",
                type="general",
                payload={"user_input": f"q_{i}"},
            )
            engine.run(request)
        elapsed = time.perf_counter() - start

        # 单次 < 50ms（mock LLM 场景）
        avg_ms = (elapsed / 100) * 1000
        assert avg_ms < 50, f"性能不达标: {avg_ms}ms/次"


# ============================================================
# Part 4: 跨服务调用链 - 多组件协作
# ============================================================
class TestCrossServiceIntegration:
    """跨服务调用链：缓存 + 评估 + 持久化"""

    def test_cache_then_evaluate_pattern(self):
        """真实场景：先查缓存，未命中再评测"""
        from unittest.mock import MagicMock

        from src.engine import EvaluationEngine
        from src.infra.cache import EvaluationCache
        from src.schemas.evaluation import EvaluationSchema

        cache = EvaluationCache(ttl_seconds=60, max_size=100)
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "cache-test"
        client.chat = MagicMock(return_value="expensive response")
        engine = EvaluationEngine(client)

        request = EvaluationSchema(
            id="cache_001",
            type="general",
            payload={"user_input": "expensive query"},
        )

        # 第一次：未命中，执行评测
        cache_key = f"eval:{request.id}"
        assert cache.get(cache_key) is None

        result = engine.run(request)
        # 缓存结果
        cache.set(cache_key, {"status": result.status.value, "score": result.response.score})

        # 第二次：命中缓存
        cached = cache.get(cache_key)
        assert cached is not None
        assert cached["status"] == result.status.value

    def test_evaluator_factory_with_runtime_registration(self):
        """场景：业务方运行时注册新评估器（插件模式）"""
        from src.domain.evaluators.base import BaseEvaluator
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        from src.engine import EvaluationEngine
        from src.schemas.evaluation import DomainResponse, EvaluationSchema

        # 业务方注册自定义评估器
        @EvaluatorFactory.register("custom_business_eval")
        class CustomBusinessEvaluator(BaseEvaluator):
            """业务方自定义评估器"""

            def evaluate(self, request):
                return DomainResponse(
                    is_valid=True,
                    score=0.95,
                    text="custom eval passed",
                )

        # 引擎自动发现并使用
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "test"
        engine = EvaluationEngine(client)
        request = EvaluationSchema(
            id="custom_001",
            type="custom_business_eval",
            payload={"data": "test"},
        )
        result = engine.run(request)
        assert result.status.value == "passed"
        assert "Custom" in result.adapter_name


# ============================================================
# Part 5: 异常链路 - 故障恢复
# ============================================================
class TestExceptionChainIntegration:
    """异常链路：评估器异常 → engine 分类 → API 响应"""

    def test_contract_error_chain_to_api(self):
        """场景：契约错误链路

        真实 BUG: run_evaluation_service 即便 engine 返回 ERROR
        仍返回 status="success"，掩盖了失败状态
        """
        from src.domain.evaluators.base import BaseEvaluator
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        from src.engine import EvaluationEngine
        from src.exceptions import ContractValidationError
        from src.schemas.evaluation import EvaluationSchema, EvaluationStatus
        from src.services.evaluator_svc import run_evaluation_service

        @EvaluatorFactory.register("contract_err_chain")
        class ContractErrEval(BaseEvaluator):
            def evaluate(self, req):
                raise ContractValidationError("字段缺失")

        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "test"

        # 引擎层：捕获并返回 ERROR 状态
        engine = EvaluationEngine(client)
        request = EvaluationSchema(id="c1", type="contract_err_chain", payload={})
        result = engine.run(request)
        assert result.status == EvaluationStatus.ERROR
        assert "字段缺失" in result.error_message
        assert result.adapter_name == "contract_validator"

        # Service 层：业务上应返回 error 状态
        result_dict = run_evaluation_service(
            {"id": "c2", "type": "contract_err_chain", "payload": {}},
            client=client,
        )
        # 关键：evaluation_status 应为 "error"
        assert result_dict["evaluation_status"] == "error"
        # 修复后：status 应为 "error"（不再掩盖失败）
        assert result_dict["status"] == "error"

    def test_unexpected_error_chain_to_api(self):
        """场景：未预期异常的传播"""
        from src.domain.evaluators.base import BaseEvaluator
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        from src.engine import EvaluationEngine
        from src.schemas.evaluation import EvaluationSchema, EvaluationStatus

        @EvaluatorFactory.register("unexpected_err")
        class UnexpectedEval(BaseEvaluator):
            def evaluate(self, req):
                raise RuntimeError("Bug in eval logic")

        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "test"
        engine = EvaluationEngine(client)
        request = EvaluationSchema(id="c1", type="unexpected_err", payload={})
        result = engine.run(request)

        # safe_evaluate 返回 DomainResponse(is_valid=False, error="EVALUATION_ERROR: ...")
        # engine 检测到 error 包含 "_ERROR"，返回 ERROR 状态
        assert result.status == EvaluationStatus.ERROR
        # 关键：内部错误信息包含在 error 字段中
        assert "EVALUATION_ERROR" in result.response.error


# ============================================================
# Part 6: 高并发业务场景
# ============================================================
class TestHighConcurrencyBusinessScenarios:
    """高并发：1000+ 并发请求下系统稳定性"""

    def test_concurrent_evaluations_same_type(self, mock_llm_client):
        """场景：100 个并发请求，相同 type（general）"""
        from src.engine import EvaluationEngine
        from src.schemas.evaluation import EvaluationSchema

        engine = EvaluationEngine(mock_llm_client)
        results = []
        errors = []
        lock = threading.Lock()
        barrier = threading.Barrier(100)

        def worker(idx):
            barrier.wait()
            try:
                request = EvaluationSchema(
                    id=f"concurrent_{idx:03d}",
                    type="general",
                    payload={"user_input": f"q_{idx}"},
                )
                result = engine.run(request)
                with lock:
                    results.append(result)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"并发评测异常: {errors[:3]}"
        assert len(results) == 100
        # 所有结果应唯一
        case_ids = [r.case_id for r in results]
        assert len(set(case_ids)) == 100

    def test_concurrent_evaluations_different_types(self, mock_llm_client):
        """场景：50 个并发请求，混合不同 type"""
        from src.domain.evaluators.base import BaseEvaluator
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        from src.engine import EvaluationEngine
        from src.schemas.evaluation import DomainResponse, EvaluationSchema

        @EvaluatorFactory.register("type_a")
        class TypeAEval(BaseEvaluator):
            def evaluate(self, req):
                return DomainResponse(is_valid=True, score=0.9)

        @EvaluatorFactory.register("type_b")
        class TypeBEval(BaseEvaluator):
            def evaluate(self, req):
                return DomainResponse(is_valid=True, score=0.8)

        engine = EvaluationEngine(mock_llm_client)
        results = []
        lock = threading.Lock()
        barrier = threading.Barrier(50)

        def worker(idx):
            barrier.wait()
            t = "type_a" if idx % 2 == 0 else "type_b"
            request = EvaluationSchema(
                id=f"mix_{idx:03d}",
                type=t,
                payload={},
            )
            result = engine.run(request)
            with lock:
                results.append((idx, t, result.adapter_name))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 50
        # 验证路由正确
        for idx, t, adapter in results:
            expected = "TypeAEval" if t == "type_a" else "TypeBEval"
            assert adapter == expected, f"路由错误: idx={idx}, type={t}, adapter={adapter}"


# ============================================================
# Part 7: 数据完整性
# ============================================================
class TestDataIntegrityBusinessScenarios:
    """数据完整性：跨层数据不丢失"""

    def test_response_data_roundtrip(self):
        """场景：DomainResponse 数据完整传递到 API 响应

        真实 BUG: service 层直接将 DomainResponse 放入 data 字段，
        但 DomainResponse 是 Pydantic Model，不支持 .get() 方法
        """
        from unittest.mock import MagicMock

        from src.services.evaluator_svc import run_evaluation_service

        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "test"
        client.chat = MagicMock(return_value="detailed response")

        # 通过 service 跑一次
        result = run_evaluation_service(
            {
                "id": "rt_001",
                "type": "general",
                "payload": {
                    "user_input": "test",
                    "expected_output": "detailed response",
                },
            },
            client=client,
        )

        # data 应包含 DomainResponse 的所有字段（已序列化为 dict）
        assert "data" in result
        data = result["data"]
        # 修复后：data 是 dict，不是 DomainResponse 对象
        assert isinstance(data, dict), f"data 应为 dict，实际类型: {type(data)}"
        assert data.get("is_valid") is True
        assert "score" in data

    def test_case_id_preserved_through_pipeline(self):
        """场景：case_id 从输入到结果全链路保持一致"""
        from unittest.mock import MagicMock

        from src.engine import EvaluationEngine
        from src.schemas.evaluation import EvaluationSchema
        from src.services.evaluator_svc import run_evaluation_service

        case_id = "preservation_test_123"
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "test"
        client.chat = MagicMock(return_value="ok")

        # API -> Service -> Engine
        result = run_evaluation_service(
            {"id": case_id, "type": "general", "payload": {"user_input": "test"}},
            client=client,
        )
        assert result["record_id"] == case_id

        # Engine 层 case_id 也一致
        engine = EvaluationEngine(client)
        request = EvaluationSchema(id=case_id, type="general", payload={"user_input": "test"})
        engine_result = engine.run(request)
        assert engine_result.case_id == case_id
