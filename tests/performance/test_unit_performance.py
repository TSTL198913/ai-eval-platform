"""
单元级性能测试

测试核心组件的性能基线，包括：
1. 评估器工厂 - 初始化、获取评估器性能
2. 评估引擎 - 同步/异步执行性能
3. 缓存层 - 读写性能
4. 数据缓冲服务 - 添加、flush性能

使用科学测量方法：
- 预热阶段：确保JIT编译和缓存预热
- 测量阶段：多次测量取统计值
- 统计指标：P50/P95/P99延迟、吞吐量、错误率
"""

import asyncio
import gc
import statistics
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

import pytest

# =====================================================================
# 配置常量
# =====================================================================

WARMUP_ITERATIONS = 5
MEASURE_ITERATIONS = 50
PERCENTILES = [50, 75, 90, 95, 99]


# =====================================================================
# 全局 Fixture
# =====================================================================


@pytest.fixture(autouse=True)
def ensure_evaluators_registered():
    """确保评估器已注册（覆盖conftest的重置）"""
    from src.domain.evaluators import auto_discover

    auto_discover(force=True)


@pytest.fixture
def stub_client():
    """提供 StubLLMClient 实例"""
    from pydantic import SecretStr

    from src.domain.models.base import ModelConfig
    from src.domain.models.stub import StubLLMClient

    config = ModelConfig(
        api_key=SecretStr("test-key"),
        model_name="stub-model",
        temperature=0.7,
        max_tokens=1024,
    )
    return StubLLMClient(config)


# =====================================================================
# 数据模型
# =====================================================================


@dataclass
class PerformanceResult:
    name: str
    iterations: int
    total_duration_ms: float
    avg_duration_ms: float
    min_duration_ms: float
    max_duration_ms: float
    std_dev_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    throughput: float
    errors: int
    error_rate: float

    def to_dict(self) -> dict:
        return asdict(self)

    def __str__(self) -> str:
        return (
            f"{self.name}: avg={self.avg_duration_ms:.2f}ms, "
            f"P50={self.p50_ms:.2f}ms, P95={self.p95_ms:.2f}ms, P99={self.p99_ms:.2f}ms, "
            f"throughput={self.throughput:.2f} req/s, errors={self.error_rate:.2f}%"
        )


# =====================================================================
# 工具函数
# =====================================================================


def calculate_percentiles(values: list[float]) -> dict[str, float]:
    if not values:
        return {f"p{p}": 0.0 for p in PERCENTILES}
    sorted_values = sorted(values)
    n = len(sorted_values)
    result = {}
    for p in PERCENTILES:
        index = (p / 100) * (n - 1)
        lower = int(index)
        upper = min(lower + 1, n - 1)
        weight = index - lower
        result[f"p{p}"] = sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight
    return result


def measure_sync(
    func: Callable[[], Any], iterations: int = MEASURE_ITERATIONS
) -> PerformanceResult:
    for _ in range(WARMUP_ITERATIONS):
        func()
    gc.collect()

    durations = []
    errors = 0
    start_total = time.perf_counter()

    for _ in range(iterations):
        start = time.perf_counter()
        try:
            func()
            durations.append((time.perf_counter() - start) * 1000)
        except Exception:
            errors += 1

    total_duration = (time.perf_counter() - start_total) * 1000
    percentiles = calculate_percentiles(durations)

    return PerformanceResult(
        name=func.__name__,
        iterations=iterations,
        total_duration_ms=total_duration,
        avg_duration_ms=sum(durations) / len(durations) if durations else 0,
        min_duration_ms=min(durations) if durations else 0,
        max_duration_ms=max(durations) if durations else 0,
        std_dev_ms=statistics.stdev(durations) if len(durations) > 1 else 0,
        p50_ms=percentiles["p50"],
        p95_ms=percentiles["p95"],
        p99_ms=percentiles["p99"],
        throughput=iterations / (total_duration / 1000) if total_duration > 0 else 0,
        errors=errors,
        error_rate=(errors / iterations) * 100,
    )


async def measure_async(
    func: Callable[[], Any], iterations: int = MEASURE_ITERATIONS
) -> PerformanceResult:
    for _ in range(WARMUP_ITERATIONS):
        await func()
    gc.collect()

    durations = []
    errors = 0
    start_total = time.perf_counter()

    for _ in range(iterations):
        start = time.perf_counter()
        try:
            await func()
            durations.append((time.perf_counter() - start) * 1000)
        except Exception:
            errors += 1

    total_duration = (time.perf_counter() - start_total) * 1000
    percentiles = calculate_percentiles(durations)

    return PerformanceResult(
        name=func.__name__,
        iterations=iterations,
        total_duration_ms=total_duration,
        avg_duration_ms=sum(durations) / len(durations) if durations else 0,
        min_duration_ms=min(durations) if durations else 0,
        max_duration_ms=max(durations) if durations else 0,
        std_dev_ms=statistics.stdev(durations) if len(durations) > 1 else 0,
        p50_ms=percentiles["p50"],
        p95_ms=percentiles["p95"],
        p99_ms=percentiles["p99"],
        throughput=iterations / (total_duration / 1000) if total_duration > 0 else 0,
        errors=errors,
        error_rate=(errors / iterations) * 100,
    )


# =====================================================================
# 评估器工厂性能测试
# =====================================================================


class TestEvaluatorFactoryPerformance:
    """评估器工厂性能测试"""

    def test_evaluator_get_performance(self):
        """获取评估器性能测试（lazy loading）"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory

        def get_evaluator():
            return EvaluatorFactory.get("general")

        result = measure_sync(get_evaluator)
        print(f"评估器获取性能: {result}")

        assert result.p95_ms < 50, f"评估器获取P95延迟过高: {result.p95_ms}ms"
        assert result.error_rate == 0, f"评估器获取错误率不为0: {result.error_rate}%"

    def test_evaluator_list_performance(self):
        """获取评估器列表性能测试"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory

        def list_evaluators():
            return EvaluatorFactory.list_evaluators()

        result = measure_sync(list_evaluators)
        print(f"评估器列表性能: {result}")

        assert result.p95_ms < 10, f"评估器列表P95延迟过高: {result.p95_ms}ms"
        assert result.error_rate == 0, f"评估器列表错误率不为0: {result.error_rate}%"

    def test_multiple_evaluator_types_get(self):
        """获取多种类型评估器性能"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory

        types = ["general", "security", "semantic", "grammar", "summary"]

        def get_random_evaluator():
            for t in types:
                EvaluatorFactory.get(t)

        result = measure_sync(get_random_evaluator, iterations=20)
        print(f"多评估器类型获取性能: {result}")

        assert result.p95_ms < 100, f"多评估器获取P95延迟过高: {result.p95_ms}ms"


# =====================================================================
# 评估引擎性能测试
# =====================================================================


class TestEvaluationEnginePerformance:
    """评估引擎性能测试"""

    def test_engine_sync_run_performance(self, stub_client):
        """同步执行性能测试"""
        from src.engine import EvaluationEngine
        from src.schemas.evaluation import EvaluationSchema

        engine = EvaluationEngine(stub_client)

        def run_evaluation():
            request = EvaluationSchema(
                id=f"test-{uuid.uuid4()}",
                type="general",
                payload={"user_input": "测试文本", "expected_output": "测试预期"},
            )
            result = engine.run(request)
            assert result.status.value in ["passed", "failed"]

        result = measure_sync(run_evaluation)
        print(f"引擎同步执行性能: {result}")

        assert result.p95_ms < 100, f"同步执行P95延迟过高: {result.p95_ms}ms"

    @pytest.mark.asyncio
    async def test_engine_async_run_performance(self, stub_client):
        """异步执行性能测试"""
        from src.engine import EvaluationEngine
        from src.schemas.evaluation import EvaluationSchema

        engine = EvaluationEngine(stub_client)

        async def run_async_evaluation():
            request = EvaluationSchema(
                id=f"test-{uuid.uuid4()}",
                type="general",
                payload={"user_input": "测试文本", "expected_output": "测试预期"},
            )
            result = await engine.run_async(request)
            assert result.status.value in ["passed", "failed"]

        result = await measure_async(run_async_evaluation)
        print(f"引擎异步执行性能: {result}")

        assert result.p95_ms < 150, f"异步执行P95延迟过高: {result.p95_ms}ms"


# =====================================================================
# 缓存层性能测试
# =====================================================================


class TestCachePerformance:
    """缓存层性能测试"""

    def test_cache_set_get_performance(self):
        """缓存读写性能测试"""
        try:
            from src.infra.cache import get_redis

            redis_client = get_redis()
            redis_client.ping()
        except Exception:
            pytest.skip("Redis不可用，跳过缓存性能测试")

        def cache_operation():
            key = f"perf_test_{uuid.uuid4()}"
            value = "test_value_12345"
            redis_client.set(key, value)
            result = redis_client.get(key)
            assert result == value.encode()
            redis_client.delete(key)

        result = measure_sync(cache_operation, iterations=100)
        print(f"缓存读写性能: {result}")

        assert result.p95_ms < 5, f"缓存P95延迟过高: {result.p95_ms}ms"

    def test_cache_get_miss_performance(self):
        """缓存未命中性能测试"""
        try:
            from src.infra.cache import get_redis

            redis_client = get_redis()
            redis_client.ping()
        except Exception:
            pytest.skip("Redis不可用，跳过缓存性能测试")

        def cache_miss_operation():
            key = f"miss_key_{uuid.uuid4()}"
            result = redis_client.get(key)
            assert result is None

        result = measure_sync(cache_miss_operation, iterations=100)
        print(f"缓存未命中性能: {result}")

        assert result.p95_ms < 5, f"缓存未命中P95延迟过高: {result.p95_ms}ms"


# =====================================================================
# 数据缓冲服务性能测试
# =====================================================================


class TestBufferServicePerformance:
    """数据缓冲服务性能测试"""

    def test_buffer_add_performance(self):
        """缓冲添加性能测试"""
        from src.schemas.evaluation import DomainResponse
        from src.schemas.schemas import EvaluationResult, EvaluationStatus
        from src.workers.tasks import EvaluationBufferService, _result_to_model

        buffer = EvaluationBufferService(batch_size=1000, flush_interval_seconds=300)

        def create_mock_result():
            response = DomainResponse(is_valid=True, text="test", score=0.8)
            return EvaluationResult(
                case_id=f"test-{uuid.uuid4()}",
                status=EvaluationStatus.PASSED,
                model_name="test-model",
                adapter_name="test-adapter",
                response=response,
                latency_ms=100.0,
            )

        def buffer_add():
            result = create_mock_result()
            db_record = _result_to_model(result)
            buffer.add(db_record)

        result = measure_sync(buffer_add, iterations=200)
        print(f"缓冲添加性能: {result}")

        assert result.p95_ms < 1, f"缓冲添加P95延迟过高: {result.p95_ms}ms"
        buffer.close_reusable_session()

    def test_buffer_flush_performance(self):
        """缓冲flush性能测试"""
        from src.schemas.evaluation import DomainResponse
        from src.schemas.schemas import EvaluationResult, EvaluationStatus
        from src.workers.tasks import EvaluationBufferService, _result_to_model

        buffer = EvaluationBufferService(batch_size=1000, flush_interval_seconds=300)

        for i in range(50):
            response = DomainResponse(is_valid=True, text="test", score=0.8)
            result = EvaluationResult(
                case_id=f"test-flush-{i}",
                status=EvaluationStatus.PASSED,
                model_name="test-model",
                adapter_name="test-adapter",
                response=response,
                latency_ms=100.0,
            )
            db_record = _result_to_model(result)
            buffer.add(db_record)

        def buffer_flush():
            buffer.flush()

        result = measure_sync(buffer_flush, iterations=10)
        print(f"缓冲flush性能: {result}")

        assert result.p95_ms < 500, f"缓冲flush P95延迟过高: {result.p95_ms}ms"
        buffer.close_reusable_session()


# =====================================================================
# 评估器执行性能测试
# =====================================================================


class TestEvaluatorExecutionPerformance:
    """评估器执行性能测试"""

    def test_general_evaluator_performance(self, stub_client):
        """通用评估器性能测试"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        from src.schemas.evaluation import EvaluationSchema

        evaluator = EvaluatorFactory.get("general", client=stub_client)

        def evaluate():
            request = EvaluationSchema(
                id=f"test-{uuid.uuid4()}",
                type="general",
                payload={"user_input": "这是一段测试文本", "expected_output": "这是预期输出"},
            )
            result = evaluator.evaluate(request)
            assert result.is_valid is not None

        result = measure_sync(evaluate, iterations=30)
        print(f"通用评估器性能: {result}")

        assert result.p95_ms < 50, f"通用评估器P95延迟过高: {result.p95_ms}ms"

    def test_security_evaluator_performance(self, stub_client):
        """安全评估器性能测试"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        from src.schemas.evaluation import EvaluationSchema

        evaluator = EvaluatorFactory.get("security", client=stub_client)

        def evaluate():
            request = EvaluationSchema(
                id=f"test-{uuid.uuid4()}",
                type="security",
                payload={"user_input": "正常的用户输入", "expected_output": "正常输出"},
            )
            result = evaluator.evaluate(request)
            assert result.is_valid is not None

        result = measure_sync(evaluate, iterations=30)
        print(f"安全评估器性能: {result}")

        assert result.p95_ms < 100, f"安全评估器P95延迟过高: {result.p95_ms}ms"

    def test_semantic_evaluator_performance(self, stub_client):
        """语义评估器性能测试"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        from src.schemas.evaluation import EvaluationSchema

        evaluator = EvaluatorFactory.get("semantic", client=stub_client)

        def evaluate():
            request = EvaluationSchema(
                id=f"test-{uuid.uuid4()}",
                type="semantic",
                payload={
                    "user_input": "机器学习是人工智能的一个分支",
                    "expected_output": "ML is a branch of AI",
                },
            )
            result = evaluator.evaluate(request)
            assert result.is_valid is not None

        result = measure_sync(evaluate, iterations=30)
        print(f"语义评估器性能: {result}")

        assert result.p95_ms < 200, f"语义评估器P95延迟过高: {result.p95_ms}ms"


# =====================================================================
# 并发性能测试
# =====================================================================


class TestConcurrentPerformance:
    """并发性能测试"""

    def test_engine_concurrent_execution(self, stub_client):
        """评估引擎并发执行性能"""
        import threading

        from src.engine import EvaluationEngine
        from src.schemas.evaluation import EvaluationSchema

        engine = EvaluationEngine(stub_client)
        results = []
        errors = 0
        lock = threading.Lock()
        total_requests = 50

        def worker():
            nonlocal errors
            request = EvaluationSchema(
                id=f"concurrent-{uuid.uuid4()}",
                type="general",
                payload={"user_input": "测试文本", "expected_output": "测试预期"},
            )
            try:
                result = engine.run(request)
                with lock:
                    results.append(result)
            except Exception:
                with lock:
                    errors += 1

        start_time = time.perf_counter()
        threads = [threading.Thread(target=worker) for _ in range(total_requests)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        total_duration = (time.perf_counter() - start_time) * 1000

        throughput = total_requests / (total_duration / 1000)
        error_rate = (errors / total_requests) * 100

        print(
            f"引擎并发性能: {total_requests}请求, {total_duration:.2f}ms, "
            f"throughput={throughput:.2f} req/s, error_rate={error_rate:.2f}%"
        )

        assert error_rate < 5, f"并发执行错误率过高: {error_rate}%"
        assert throughput > 10, f"并发吞吐量过低: {throughput} req/s"

    @pytest.mark.asyncio
    async def test_engine_async_concurrent_execution(self, stub_client):
        """评估引擎异步并发执行性能"""
        from src.engine import EvaluationEngine
        from src.schemas.evaluation import EvaluationSchema

        engine = EvaluationEngine(stub_client)
        total_requests = 50

        async def worker():
            request = EvaluationSchema(
                id=f"async-concurrent-{uuid.uuid4()}",
                type="general",
                payload={"user_input": "测试文本", "expected_output": "测试预期"},
            )
            return await engine.run_async(request)

        start_time = time.perf_counter()
        tasks = [worker() for _ in range(total_requests)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_duration = (time.perf_counter() - start_time) * 1000

        errors = sum(1 for r in results if isinstance(r, Exception))
        throughput = total_requests / (total_duration / 1000)
        error_rate = (errors / total_requests) * 100

        print(
            f"引擎异步并发性能: {total_requests}请求, {total_duration:.2f}ms, "
            f"throughput={throughput:.2f} req/s, error_rate={error_rate:.2f}%"
        )

        assert error_rate < 5, f"异步并发执行错误率过高: {error_rate}%"
        assert throughput > 20, f"异步并发吞吐量过低: {throughput} req/s"
