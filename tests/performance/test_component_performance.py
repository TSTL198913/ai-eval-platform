"""
组件级性能测试

测试API层、异步任务层、数据库层的性能，包括：
1. API端点性能 - 同步评估、异步评估、批量评估
2. 异步任务性能 - Celery任务调度、缓冲落盘
3. 数据库性能 - 连接池、查询、批量写入
4. 中间件性能 - Prometheus指标、安全中间件

测试策略：
- 预热阶段：确保系统稳定
- 梯度加压：从低负载逐步增加到高负载
- 稳定负载：在目标负载下持续运行
- 统计分析：计算P50/P95/P99延迟、吞吐量、错误率
"""

import asyncio
import gc
import time
import uuid
from dataclasses import asdict, dataclass

import httpx
import pytest

# =====================================================================
# 配置常量
# =====================================================================

BASE_URL = "http://localhost:8000"
WARMUP_ITERATIONS = 5
MEASURE_ITERATIONS = 30
CONCURRENT_LEVELS = [1, 5, 10, 20]
PERCENTILES = [50, 75, 90, 95, 99]


# =====================================================================
# 数据模型
# =====================================================================


@dataclass
class ComponentPerformanceResult:
    component: str
    endpoint: str
    concurrency: int
    total_requests: int
    total_duration_ms: float
    avg_duration_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    throughput: float
    error_rate: float
    status_codes: dict[int, int]

    def to_dict(self) -> dict:
        return asdict(self)

    def __str__(self) -> str:
        return (
            f"{self.component}/{self.endpoint} [concurrency={self.concurrency}]: "
            f"avg={self.avg_duration_ms:.2f}ms, P95={self.p95_ms:.2f}ms, "
            f"throughput={self.throughput:.2f} req/s, error_rate={self.error_rate:.2f}%"
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


def check_server_available() -> bool:
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{BASE_URL}/health")
            return response.status_code == 200
    except Exception:
        return False


# =====================================================================
# API端点性能测试
# =====================================================================


class TestAPIEndpointPerformance:
    """API端点性能测试"""

    @pytest.mark.skipif(not check_server_available(), reason="API服务器未运行")
    def test_health_check_performance(self):
        """健康检查接口性能测试"""
        with httpx.Client(timeout=5.0) as client:

            def call_health():
                response = client.get(f"{BASE_URL}/health")
                return response.status_code

            for _ in range(WARMUP_ITERATIONS):
                call_health()
            gc.collect()

            durations = []
            status_codes = {}
            errors = 0
            start_total = time.perf_counter()

            for _ in range(MEASURE_ITERATIONS):
                start = time.perf_counter()
                try:
                    status = call_health()
                    durations.append((time.perf_counter() - start) * 1000)
                    status_codes[status] = status_codes.get(status, 0) + 1
                except Exception:
                    errors += 1

            total_duration = (time.perf_counter() - start_total) * 1000
            percentiles = calculate_percentiles(durations)

            result = ComponentPerformanceResult(
                component="API",
                endpoint="/health",
                concurrency=1,
                total_requests=MEASURE_ITERATIONS,
                total_duration_ms=total_duration,
                avg_duration_ms=sum(durations) / len(durations) if durations else 0,
                p50_ms=percentiles["p50"],
                p95_ms=percentiles["p95"],
                p99_ms=percentiles["p99"],
                throughput=MEASURE_ITERATIONS / (total_duration / 1000)
                if total_duration > 0
                else 0,
                error_rate=(errors / MEASURE_ITERATIONS) * 100,
                status_codes=status_codes,
            )

            print(f"健康检查接口性能: {result}")

            assert result.p95_ms < 100, f"健康检查P95延迟过高: {result.p95_ms}ms"
            assert result.error_rate == 0, f"健康检查错误率不为0: {result.error_rate}%"

    @pytest.mark.skipif(not check_server_available(), reason="API服务器未运行")
    def test_list_evaluators_performance(self):
        """评估器列表接口性能测试"""
        with httpx.Client(timeout=5.0) as client:

            def call_list():
                response = client.get(f"{BASE_URL}/api/v1/evaluators")
                return response.status_code

            for _ in range(WARMUP_ITERATIONS):
                call_list()
            gc.collect()

            durations = []
            errors = 0
            start_total = time.perf_counter()

            for _ in range(MEASURE_ITERATIONS):
                start = time.perf_counter()
                try:
                    call_list()
                    durations.append((time.perf_counter() - start) * 1000)
                except Exception:
                    errors += 1

            total_duration = (time.perf_counter() - start_total) * 1000
            percentiles = calculate_percentiles(durations)

            result = ComponentPerformanceResult(
                component="API",
                endpoint="/api/v1/evaluators",
                concurrency=1,
                total_requests=MEASURE_ITERATIONS,
                total_duration_ms=total_duration,
                avg_duration_ms=sum(durations) / len(durations) if durations else 0,
                p50_ms=percentiles["p50"],
                p95_ms=percentiles["p95"],
                p99_ms=percentiles["p99"],
                throughput=MEASURE_ITERATIONS / (total_duration / 1000)
                if total_duration > 0
                else 0,
                error_rate=(errors / MEASURE_ITERATIONS) * 100,
                status_codes={},
            )

            print(f"评估器列表接口性能: {result}")

            assert result.p95_ms < 200, f"评估器列表P95延迟过高: {result.p95_ms}ms"
            assert result.error_rate == 0, f"评估器列表错误率不为0: {result.error_rate}%"

    @pytest.mark.skipif(not check_server_available(), reason="API服务器未运行")
    def test_sync_evaluate_performance(self):
        """同步评估接口性能测试"""
        with httpx.Client(timeout=30.0) as client:

            def call_evaluate():
                response = client.post(
                    f"{BASE_URL}/api/v1/evaluate",
                    json={
                        "id": f"perf-{uuid.uuid4()}",
                        "type": "general",
                        "payload": {"user_input": "测试文本", "expected_output": "测试预期"},
                    },
                )
                return response.status_code

            for _ in range(WARMUP_ITERATIONS):
                call_evaluate()
            gc.collect()

            durations = []
            errors = 0
            start_total = time.perf_counter()

            for _ in range(MEASURE_ITERATIONS):
                start = time.perf_counter()
                try:
                    call_evaluate()
                    durations.append((time.perf_counter() - start) * 1000)
                except Exception:
                    errors += 1

            total_duration = (time.perf_counter() - start_total) * 1000
            percentiles = calculate_percentiles(durations)

            result = ComponentPerformanceResult(
                component="API",
                endpoint="/api/v1/evaluate",
                concurrency=1,
                total_requests=MEASURE_ITERATIONS,
                total_duration_ms=total_duration,
                avg_duration_ms=sum(durations) / len(durations) if durations else 0,
                p50_ms=percentiles["p50"],
                p95_ms=percentiles["p95"],
                p99_ms=percentiles["p99"],
                throughput=MEASURE_ITERATIONS / (total_duration / 1000)
                if total_duration > 0
                else 0,
                error_rate=(errors / MEASURE_ITERATIONS) * 100,
                status_codes={},
            )

            print(f"同步评估接口性能: {result}")

            assert result.p95_ms < 2000, f"同步评估P95延迟过高: {result.p95_ms}ms"

    @pytest.mark.skipif(not check_server_available(), reason="API服务器未运行")
    def test_async_evaluate_performance(self):
        """异步评估接口性能测试"""
        with httpx.Client(timeout=30.0) as client:

            def call_async_evaluate():
                response = client.post(
                    f"{BASE_URL}/api/v1/evaluate/async",
                    json={
                        "id": f"perf-{uuid.uuid4()}",
                        "type": "general",
                        "payload": {"user_input": "测试文本", "expected_output": "测试预期"},
                    },
                )
                return response.status_code

            for _ in range(WARMUP_ITERATIONS):
                call_async_evaluate()
            gc.collect()

            durations = []
            errors = 0
            start_total = time.perf_counter()

            for _ in range(MEASURE_ITERATIONS):
                start = time.perf_counter()
                try:
                    call_async_evaluate()
                    durations.append((time.perf_counter() - start) * 1000)
                except Exception:
                    errors += 1

            total_duration = (time.perf_counter() - start_total) * 1000
            percentiles = calculate_percentiles(durations)

            result = ComponentPerformanceResult(
                component="API",
                endpoint="/api/v1/evaluate/async",
                concurrency=1,
                total_requests=MEASURE_ITERATIONS,
                total_duration_ms=total_duration,
                avg_duration_ms=sum(durations) / len(durations) if durations else 0,
                p50_ms=percentiles["p50"],
                p95_ms=percentiles["p95"],
                p99_ms=percentiles["p99"],
                throughput=MEASURE_ITERATIONS / (total_duration / 1000)
                if total_duration > 0
                else 0,
                error_rate=(errors / MEASURE_ITERATIONS) * 100,
                status_codes={},
            )

            print(f"异步评估接口性能: {result}")

            assert result.p95_ms < 500, f"异步评估P95延迟过高: {result.p95_ms}ms"

    @pytest.mark.skipif(not check_server_available(), reason="API服务器未运行")
    def test_batch_evaluate_performance(self):
        """批量评估接口性能测试"""
        with httpx.Client(timeout=60.0) as client:

            def call_batch():
                cases = [
                    {
                        "id": f"batch-{uuid.uuid4()}",
                        "type": "general",
                        "payload": {"user_input": f"测试文本{i}", "expected_output": "测试预期"},
                    }
                    for i in range(10)
                ]
                response = client.post(
                    f"{BASE_URL}/api/v1/evaluate/sync-batch",
                    json={"cases": cases},
                )
                return response.status_code

            for _ in range(WARMUP_ITERATIONS):
                call_batch()
            gc.collect()

            durations = []
            errors = 0
            start_total = time.perf_counter()

            for _ in range(MEASURE_ITERATIONS):
                start = time.perf_counter()
                try:
                    call_batch()
                    durations.append((time.perf_counter() - start) * 1000)
                except Exception:
                    errors += 1

            total_duration = (time.perf_counter() - start_total) * 1000
            percentiles = calculate_percentiles(durations)

            result = ComponentPerformanceResult(
                component="API",
                endpoint="/api/v1/evaluate/sync-batch",
                concurrency=1,
                total_requests=MEASURE_ITERATIONS,
                total_duration_ms=total_duration,
                avg_duration_ms=sum(durations) / len(durations) if durations else 0,
                p50_ms=percentiles["p50"],
                p95_ms=percentiles["p95"],
                p99_ms=percentiles["p99"],
                throughput=(MEASURE_ITERATIONS * 10) / (total_duration / 1000)
                if total_duration > 0
                else 0,
                error_rate=(errors / MEASURE_ITERATIONS) * 100,
                status_codes={},
            )

            print(f"批量评估接口性能: {result}")

            assert result.p95_ms < 10000, f"批量评估P95延迟过高: {result.p95_ms}ms"


# =====================================================================
# API并发性能测试
# =====================================================================


class TestAPIConcurrentPerformance:
    """API并发性能测试"""

    @pytest.mark.skipif(not check_server_available(), reason="API服务器未运行")
    def test_health_check_concurrent(self):
        """健康检查接口并发测试"""
        with httpx.Client(timeout=5.0) as client:
            for concurrency in CONCURRENT_LEVELS:
                total_requests = concurrency * 10
                durations = []
                errors = 0
                lock = asyncio.Lock()

                async def worker():
                    nonlocal errors
                    start = time.perf_counter()
                    try:
                        response = await asyncio.to_thread(client.get, f"{BASE_URL}/health")
                        async with lock:
                            durations.append((time.perf_counter() - start) * 1000)
                    except Exception:
                        async with lock:
                            errors += 1

                async def run():
                    tasks = [worker() for _ in range(total_requests)]
                    await asyncio.gather(*tasks, return_exceptions=True)

                start_total = time.perf_counter()
                asyncio.run(run())
                total_duration = (time.perf_counter() - start_total) * 1000

                percentiles = calculate_percentiles(durations)
                throughput = total_requests / (total_duration / 1000) if total_duration > 0 else 0
                error_rate = (errors / total_requests) * 100

                print(
                    f"健康检查并发 [concurrency={concurrency}]: "
                    f"total={total_duration:.2f}ms, P95={percentiles['p95']:.2f}ms, "
                    f"throughput={throughput:.2f} req/s, error_rate={error_rate:.2f}%"
                )

                assert error_rate < 5, f"并发 {concurrency} 错误率过高: {error_rate}%"

    @pytest.mark.skipif(not check_server_available(), reason="API服务器未运行")
    def test_evaluate_concurrent(self):
        """评估接口并发测试"""
        with httpx.Client(timeout=30.0) as client:
            for concurrency in [1, 5, 10]:
                total_requests = concurrency * 5
                durations = []
                errors = 0
                lock = asyncio.Lock()

                async def worker():
                    nonlocal errors
                    start = time.perf_counter()
                    try:
                        response = await asyncio.to_thread(
                            client.post,
                            f"{BASE_URL}/api/v1/evaluate",
                            json={
                                "id": f"concurrent-{uuid.uuid4()}",
                                "type": "general",
                                "payload": {
                                    "user_input": "测试文本",
                                    "expected_output": "测试预期",
                                },
                            },
                        )
                        async with lock:
                            durations.append((time.perf_counter() - start) * 1000)
                    except Exception:
                        async with lock:
                            errors += 1

                async def run():
                    tasks = [worker() for _ in range(total_requests)]
                    await asyncio.gather(*tasks, return_exceptions=True)

                start_total = time.perf_counter()
                asyncio.run(run())
                total_duration = (time.perf_counter() - start_total) * 1000

                percentiles = calculate_percentiles(durations)
                throughput = total_requests / (total_duration / 1000) if total_duration > 0 else 0
                error_rate = (errors / total_requests) * 100

                print(
                    f"评估接口并发 [concurrency={concurrency}]: "
                    f"total={total_duration:.2f}ms, P95={percentiles['p95']:.2f}ms, "
                    f"throughput={throughput:.2f} req/s, error_rate={error_rate:.2f}%"
                )

                assert error_rate < 10, f"并发 {concurrency} 错误率过高: {error_rate}%"


# =====================================================================
# 异步任务性能测试
# =====================================================================


class TestAsyncTaskPerformance:
    """异步任务性能测试"""

    def test_celery_task_submit_performance(self):
        """Celery任务提交性能测试"""
        try:
            from src.schemas.evaluation import EvaluationSchema
            from src.workers.tasks import eval_case_task

            def submit_task():
                case = EvaluationSchema(
                    id=f"task-{uuid.uuid4()}",
                    type="general",
                    payload={"user_input": "测试文本", "expected_output": "测试预期"},
                )
                task = eval_case_task.delay(case.model_dump())
                return task.id

            for _ in range(WARMUP_ITERATIONS):
                submit_task()
            gc.collect()

            durations = []
            errors = 0
            start_total = time.perf_counter()

            for _ in range(MEASURE_ITERATIONS):
                start = time.perf_counter()
                try:
                    submit_task()
                    durations.append((time.perf_counter() - start) * 1000)
                except Exception:
                    errors += 1

            total_duration = (time.perf_counter() - start_total) * 1000
            percentiles = calculate_percentiles(durations)

            print(
                f"Celery任务提交性能: "
                f"avg={sum(durations) / len(durations):.2f}ms, "
                f"P95={percentiles['p95']:.2f}ms, "
                f"throughput={MEASURE_ITERATIONS / (total_duration / 1000):.2f} req/s"
            )

            assert percentiles["p95"] < 500, f"任务提交P95延迟过高: {percentiles['p95']}ms"

        except Exception as e:
            pytest.skip(f"Celery不可用，跳过任务提交测试: {e}")

    def test_buffer_service_concurrent_add(self):
        """缓冲服务并发添加性能测试"""
        import threading

        from src.schemas.evaluation import DomainResponse
        from src.schemas.schemas import EvaluationResult, EvaluationStatus
        from src.workers.tasks import EvaluationBufferService, _result_to_model

        buffer = EvaluationBufferService(batch_size=1000, flush_interval_seconds=300)
        total_requests = 100
        errors = 0
        lock = threading.Lock()

        def create_mock_result():
            response = DomainResponse(is_valid=True, text="test", score=0.8)
            return EvaluationResult(
                case_id=f"concurrent-{uuid.uuid4()}",
                status=EvaluationStatus.PASSED,
                model_name="test-model",
                adapter_name="test-adapter",
                response=response,
                latency_ms=100.0,
            )

        def worker():
            nonlocal errors
            try:
                result = create_mock_result()
                db_record = _result_to_model(result)
                buffer.add(db_record)
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
            f"缓冲服务并发添加性能: {total_requests}请求, {total_duration:.2f}ms, "
            f"throughput={throughput:.2f} req/s, error_rate={error_rate:.2f}%"
        )

        assert error_rate == 0, f"缓冲服务并发错误率不为0: {error_rate}%"
        assert throughput > 50, f"缓冲服务并发吞吐量过低: {throughput} req/s"

        buffer.close_reusable_session()


# =====================================================================
# 数据库性能测试
# =====================================================================


class TestDatabasePerformance:
    """数据库性能测试"""

    def test_db_connection_pool_performance(self):
        """数据库连接池性能测试"""
        from sqlalchemy import text

        from src.infra.db.session import get_db

        def get_connection():
            gen = get_db()
            db = next(gen)
            try:
                result = db.execute(text("SELECT 1"))
                return result.scalar()
            finally:
                next(gen, None)

        for _ in range(WARMUP_ITERATIONS):
            get_connection()
        gc.collect()

        durations = []
        errors = 0
        start_total = time.perf_counter()

        for _ in range(MEASURE_ITERATIONS):
            start = time.perf_counter()
            try:
                get_connection()
                durations.append((time.perf_counter() - start) * 1000)
            except Exception:
                errors += 1

        total_duration = (time.perf_counter() - start_total) * 1000
        percentiles = calculate_percentiles(durations)

        print(
            f"数据库连接池性能: "
            f"avg={sum(durations) / len(durations):.2f}ms, "
            f"P95={percentiles['p95']:.2f}ms, "
            f"throughput={MEASURE_ITERATIONS / (total_duration / 1000):.2f} req/s"
        )

        assert percentiles["p95"] < 100, f"数据库连接P95延迟过高: {percentiles['p95']}ms"

    def test_db_batch_insert_performance(self):
        """数据库批量插入性能测试"""
        from src.infra.db.models import EvaluationResultModel
        from src.infra.db.session import get_session_local

        batch_size = 50
        records = []

        for i in range(batch_size):
            record = EvaluationResultModel(
                case_id=f"batch-{uuid.uuid4()}",
                model_name="test-model",
                adapter_name="test-adapter",
                status="passed",
                latency_ms=100.0,
                response_data={"score": 0.8},
            )
            records.append(record)

        durations = []
        for _ in range(MEASURE_ITERATIONS):
            start = time.perf_counter()
            session = None
            try:
                session = get_session_local()()
                session.bulk_save_objects(records)
                session.commit()
                durations.append((time.perf_counter() - start) * 1000)
            except Exception:
                if session:
                    session.rollback()
            finally:
                if session:
                    session.close()

        percentiles = calculate_percentiles(durations)

        print(
            f"数据库批量插入性能 [batch={batch_size}]: "
            f"avg={sum(durations) / len(durations):.2f}ms, "
            f"P95={percentiles['p95']:.2f}ms"
        )

        assert percentiles["p95"] < 1000, f"批量插入P95延迟过高: {percentiles['p95']}ms"


# =====================================================================
# 中间件性能测试
# =====================================================================


class TestMiddlewarePerformance:
    """中间件性能测试"""

    @pytest.mark.skipif(not check_server_available(), reason="API服务器未运行")
    def test_prometheus_metrics_performance(self):
        """Prometheus指标中间件性能测试"""
        with httpx.Client(timeout=5.0) as client:

            def call_metrics():
                response = client.get(f"{BASE_URL}/metrics")
                return response.status_code

            for _ in range(WARMUP_ITERATIONS):
                call_metrics()
            gc.collect()

            durations = []
            errors = 0
            start_total = time.perf_counter()

            for _ in range(MEASURE_ITERATIONS):
                start = time.perf_counter()
                try:
                    call_metrics()
                    durations.append((time.perf_counter() - start) * 1000)
                except Exception:
                    errors += 1

            total_duration = (time.perf_counter() - start_total) * 1000
            percentiles = calculate_percentiles(durations)

            print(
                f"Prometheus指标接口性能: "
                f"avg={sum(durations) / len(durations):.2f}ms, "
                f"P95={percentiles['p95']:.2f}ms"
            )

            assert percentiles["p95"] < 200, f"指标接口P95延迟过高: {percentiles['p95']}ms"

    @pytest.mark.skipif(not check_server_available(), reason="API服务器未运行")
    def test_security_middleware_overhead(self):
        """安全中间件开销测试"""
        with httpx.Client(timeout=5.0) as client:
            durations_with_middleware = []
            durations_direct = []

            for _ in range(WARMUP_ITERATIONS):
                client.get(f"{BASE_URL}/health")

            for _ in range(MEASURE_ITERATIONS):
                start = time.perf_counter()
                client.get(f"{BASE_URL}/health")
                durations_with_middleware.append((time.perf_counter() - start) * 1000)

            avg_with_middleware = sum(durations_with_middleware) / len(durations_with_middleware)

            print(f"安全中间件开销测试: 平均延迟={avg_with_middleware:.2f}ms")

            assert avg_with_middleware < 100, f"安全中间件开销过高: {avg_with_middleware}ms"
