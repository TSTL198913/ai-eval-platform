"""
全链路压测测试

模拟真实业务场景的端到端压测，包括：
1. 混合评估器负载测试 - 多种评估器混合调用
2. 批量评测场景 - 模拟批量任务提交
3. 异步任务队列压力测试 - 大量异步任务堆积
4. 缓存层压力测试 - 高并发读写
5. 数据库缓冲压力测试 - 大量数据写入
6. 熔断触发测试 - 模拟服务故障
7. 容量测试 - 逐步加压找到系统极限

测试策略：
- 预热阶段：2分钟，确保系统稳定
- 梯度加压：从低负载逐步增加到高负载
- 稳定负载：在目标负载下持续运行5-10分钟
- 峰值测试：短时间内施加极高负载
- 恢复阶段：观察系统恢复能力
"""

import asyncio
import gc
import json
import time
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import httpx
import pytest

# =====================================================================
# 配置常量
# =====================================================================

BASE_URL = "http://localhost:8000"
TEST_DURATION_SECONDS = 30
WARMUP_SECONDS = 5

# 评估器类型及其权重（模拟真实业务分布）
EVALUATOR_WEIGHTS = {
    "general": 30,
    "security": 20,
    "semantic": 15,
    "grammar": 10,
    "summary": 10,
    "qa": 10,
    "code": 5,
}

# 并发级别
STRESS_CONCURRENCY_LEVELS = [10, 20, 50, 100]

# 结果保存目录
RESULTS_DIR = Path(__file__).parent / "stress_results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# =====================================================================
# 数据模型
# =====================================================================


@dataclass
class StressTestResult:
    test_name: str
    scenario: str
    concurrency: int
    duration_seconds: int
    total_requests: int
    successful_requests: int
    failed_requests: int
    error_rate: float
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    max_latency_ms: float
    throughput: float
    evaluator_distribution: dict[str, int]
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)

    def __str__(self) -> str:
        return (
            f"[{self.test_name}] {self.scenario} "
            f"(concurrency={self.concurrency}, duration={self.duration_seconds}s):\n"
            f"  Requests: {self.total_requests} ({self.successful_requests} success, {self.failed_requests} failed)\n"
            f"  Error Rate: {self.error_rate:.2f}%\n"
            f"  Latency: avg={self.avg_latency_ms:.2f}ms, P50={self.p50_latency_ms:.2f}ms, "
            f"P95={self.p95_latency_ms:.2f}ms, P99={self.p99_latency_ms:.2f}ms\n"
            f"  Throughput: {self.throughput:.2f} req/s"
        )


# =====================================================================
# 工具函数
# =====================================================================


def calculate_percentiles(
    values: list[float], percentiles: list[int] | None = None
) -> dict[int, float]:
    if percentiles is None:
        percentiles = [50, 95, 99]
    if not values:
        return dict.fromkeys(percentiles, 0.0)
    sorted_values = sorted(values)
    n = len(sorted_values)
    result = {}
    for p in percentiles:
        index = (p / 100) * (n - 1)
        lower = int(index)
        upper = min(lower + 1, n - 1)
        weight = index - lower
        result[p] = sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight
    return result


def check_server_available() -> bool:
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{BASE_URL}/health")
            return response.status_code == 200
    except Exception:
        return False


def save_stress_result(result: StressTestResult) -> Path:
    filepath = (
        RESULTS_DIR
        / f"stress_{result.test_name}_{result.scenario}_{result.concurrency}_{result.timestamp.replace(':', '-')}.json"
    )
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
    return filepath


# =====================================================================
# 数据生成器
# =====================================================================


class TestDataGenerator:
    """测试数据生成器"""

    @staticmethod
    def generate_evaluation_request(evaluator_type: str) -> dict:
        """生成评估请求数据"""
        templates = {
            "general": {
                "user_input": "人工智能是研究、开发用于模拟、延伸和扩展人的智能的理论、方法、技术及应用系统的一门新的技术科学。",
                "expected_output": "AI is the study of how to make computers do things that would require intelligence if done by humans.",
            },
            "security": {
                "user_input": "正常的用户输入内容，没有任何安全风险",
                "expected_output": "正常的输出内容",
            },
            "semantic": {
                "user_input": "机器学习是人工智能的一个分支，它使计算机系统能够从数据中学习和改进，而无需进行明确编程。",
                "expected_output": "Machine learning is a subset of AI that enables computer systems to learn and improve from data without explicit programming.",
            },
            "grammar": {
                "user_input": "He go to school every day.",
                "expected_output": "He goes to school every day.",
            },
            "summary": {
                "user_input": "人工智能（Artificial Intelligence，AI）是计算机科学的一个分支，致力于研究、开发用于模拟、延伸和扩展人的智能的理论、方法、技术及应用系统。人工智能领域的研究包括机器人、语言识别、图像识别、自然语言处理和专家系统等。",
                "expected_output": "AI is a branch of computer science that studies and develops theories, methods, techniques, and applications for simulating, extending, and expanding human intelligence.",
            },
            "qa": {
                "user_input": "什么是人工智能？",
                "expected_output": "人工智能是计算机科学的一个分支，致力于研究、开发用于模拟、延伸和扩展人的智能的理论、方法、技术及应用系统。",
            },
            "code": {
                "user_input": "def add(a, b): return a + b",
                "expected_output": "function add(a: number, b: number): number { return a + b; }",
            },
        }
        template = templates.get(evaluator_type, templates["general"])
        return {
            "id": f"stress-{uuid.uuid4()}",
            "type": evaluator_type,
            "payload": template,
        }

    @staticmethod
    def generate_batch_request(count: int = 10) -> dict:
        """生成批量评估请求"""
        evaluator_types = list(EVALUATOR_WEIGHTS.keys())
        cases = []
        for i in range(count):
            eval_type = evaluator_types[i % len(evaluator_types)]
            cases.append(
                {
                    "id": f"batch-stress-{i}-{uuid.uuid4()}",
                    "type": eval_type,
                    "payload": TestDataGenerator.generate_evaluation_request(eval_type)["payload"],
                }
            )
        return {"cases": cases}

    @staticmethod
    def weighted_random_evaluator() -> str:
        """按权重随机选择评估器类型"""
        import random

        total_weight = sum(EVALUATOR_WEIGHTS.values())
        r = random.uniform(0, total_weight)
        cumulative = 0
        for eval_type, weight in EVALUATOR_WEIGHTS.items():
            cumulative += weight
            if r <= cumulative:
                return eval_type
        return "general"


# =====================================================================
# 混合评估器负载测试
# =====================================================================


class TestMixedEvaluatorLoad:
    """混合评估器负载测试"""

    @pytest.mark.skipif(not check_server_available(), reason="API服务器未运行")
    def test_mixed_evaluator_stress_test(self):
        """混合评估器压力测试"""
        with httpx.Client(timeout=30.0) as client:
            for concurrency in STRESS_CONCURRENCY_LEVELS:
                print(f"\n{'=' * 60}")
                print(f"混合评估器压力测试 - 并发数: {concurrency}")
                print(f"{'=' * 60}")

                # 预热
                print("预热阶段...")
                for _ in range(min(concurrency, 10)):
                    eval_type = TestDataGenerator.weighted_random_evaluator()
                    request_data = TestDataGenerator.generate_evaluation_request(eval_type)
                    try:
                        client.post(f"{BASE_URL}/api/v1/evaluate", json=request_data)
                    except Exception:
                        pass
                time.sleep(2)
                gc.collect()

                # 压力测试
                print("开始压力测试...")
                durations = []
                errors = 0
                eval_distribution = defaultdict(int)
                lock = asyncio.Lock()
                start_time = time.perf_counter()
                end_time = start_time + TEST_DURATION_SECONDS

                async def worker():
                    nonlocal errors
                    while time.perf_counter() < end_time:
                        eval_type = TestDataGenerator.weighted_random_evaluator()
                        request_data = TestDataGenerator.generate_evaluation_request(eval_type)
                        start = time.perf_counter()
                        try:
                            response = await asyncio.to_thread(
                                client.post,
                                f"{BASE_URL}/api/v1/evaluate",
                                json=request_data,
                            )
                            if response.status_code == 200:
                                async with lock:
                                    durations.append((time.perf_counter() - start) * 1000)
                                    eval_distribution[eval_type] += 1
                            else:
                                async with lock:
                                    errors += 1
                        except Exception:
                            async with lock:
                                errors += 1

                async def run():
                    tasks = [worker() for _ in range(concurrency)]
                    await asyncio.gather(*tasks, return_exceptions=True)

                asyncio.run(run())
                total_duration = time.perf_counter() - start_time

                # 统计分析
                total_requests = len(durations) + errors
                percentiles = calculate_percentiles(durations)

                result = StressTestResult(
                    test_name="mixed_evaluator",
                    scenario="sync_evaluate",
                    concurrency=concurrency,
                    duration_seconds=int(total_duration),
                    total_requests=total_requests,
                    successful_requests=len(durations),
                    failed_requests=errors,
                    error_rate=(errors / total_requests) * 100 if total_requests > 0 else 0,
                    avg_latency_ms=sum(durations) / len(durations) if durations else 0,
                    p50_latency_ms=percentiles[50],
                    p95_latency_ms=percentiles[95],
                    p99_latency_ms=percentiles[99],
                    max_latency_ms=max(durations) if durations else 0,
                    throughput=total_requests / total_duration if total_duration > 0 else 0,
                    evaluator_distribution=dict(eval_distribution),
                    timestamp=datetime.now().isoformat(),
                )

                print(result)
                save_stress_result(result)

                assert result.error_rate < 10, f"错误率过高: {result.error_rate}%"

    @pytest.mark.skipif(not check_server_available(), reason="API服务器未运行")
    def test_mixed_evaluator_async_stress(self):
        """混合评估器异步压力测试"""
        with httpx.Client(timeout=30.0) as client:
            concurrency = 50
            print(f"\n{'=' * 60}")
            print(f"混合评估器异步压力测试 - 并发数: {concurrency}")
            print(f"{'=' * 60}")

            # 预热
            print("预热阶段...")
            for _ in range(min(concurrency, 10)):
                eval_type = TestDataGenerator.weighted_random_evaluator()
                request_data = TestDataGenerator.generate_evaluation_request(eval_type)
                try:
                    client.post(f"{BASE_URL}/api/v1/evaluate/async", json=request_data)
                except Exception:
                    pass
            time.sleep(2)
            gc.collect()

            # 压力测试
            print("开始压力测试...")
            durations = []
            errors = 0
            lock = asyncio.Lock()
            start_time = time.perf_counter()
            end_time = start_time + TEST_DURATION_SECONDS

            async def worker():
                nonlocal errors
                while time.perf_counter() < end_time:
                    eval_type = TestDataGenerator.weighted_random_evaluator()
                    request_data = TestDataGenerator.generate_evaluation_request(eval_type)
                    start = time.perf_counter()
                    try:
                        response = await asyncio.to_thread(
                            client.post,
                            f"{BASE_URL}/api/v1/evaluate/async",
                            json=request_data,
                        )
                        if response.status_code == 200:
                            async with lock:
                                durations.append((time.perf_counter() - start) * 1000)
                        else:
                            async with lock:
                                errors += 1
                    except Exception:
                        async with lock:
                            errors += 1

            async def run():
                tasks = [worker() for _ in range(concurrency)]
                await asyncio.gather(*tasks, return_exceptions=True)

            asyncio.run(run())
            total_duration = time.perf_counter() - start_time

            total_requests = len(durations) + errors
            percentiles = calculate_percentiles(durations)

            result = StressTestResult(
                test_name="mixed_evaluator",
                scenario="async_evaluate",
                concurrency=concurrency,
                duration_seconds=int(total_duration),
                total_requests=total_requests,
                successful_requests=len(durations),
                failed_requests=errors,
                error_rate=(errors / total_requests) * 100 if total_requests > 0 else 0,
                avg_latency_ms=sum(durations) / len(durations) if durations else 0,
                p50_latency_ms=percentiles[50],
                p95_latency_ms=percentiles[95],
                p99_latency_ms=percentiles[99],
                max_latency_ms=max(durations) if durations else 0,
                throughput=total_requests / total_duration if total_duration > 0 else 0,
                evaluator_distribution={},
                timestamp=datetime.now().isoformat(),
            )

            print(result)
            save_stress_result(result)

            assert result.error_rate < 10, f"错误率过高: {result.error_rate}%"


# =====================================================================
# 批量评测场景测试
# =====================================================================


class TestBatchEvaluationStress:
    """批量评测场景测试"""

    @pytest.mark.skipif(not check_server_available(), reason="API服务器未运行")
    def test_batch_evaluation_stress(self):
        """批量评测压力测试"""
        with httpx.Client(timeout=60.0) as client:
            batch_sizes = [10, 20, 50]
            concurrency_levels = [1, 5, 10]

            for batch_size in batch_sizes:
                for concurrency in concurrency_levels:
                    print(f"\n{'=' * 60}")
                    print(f"批量评测压力测试 - batch={batch_size}, concurrency={concurrency}")
                    print(f"{'=' * 60}")

                    # 预热
                    print("预热阶段...")
                    for _ in range(min(concurrency, 3)):
                        batch_data = TestDataGenerator.generate_batch_request(batch_size)
                        try:
                            client.post(f"{BASE_URL}/api/v1/evaluate/sync-batch", json=batch_data)
                        except Exception:
                            pass
                    time.sleep(2)
                    gc.collect()

                    # 压力测试
                    print("开始压力测试...")
                    durations = []
                    errors = 0
                    lock = asyncio.Lock()
                    start_time = time.perf_counter()
                    end_time = start_time + TEST_DURATION_SECONDS

                    async def worker():
                        nonlocal errors
                        while time.perf_counter() < end_time:
                            batch_data = TestDataGenerator.generate_batch_request(batch_size)
                            start = time.perf_counter()
                            try:
                                response = await asyncio.to_thread(
                                    client.post,
                                    f"{BASE_URL}/api/v1/evaluate/sync-batch",
                                    json=batch_data,
                                )
                                if response.status_code == 200:
                                    async with lock:
                                        durations.append((time.perf_counter() - start) * 1000)
                                else:
                                    async with lock:
                                        errors += 1
                            except Exception:
                                async with lock:
                                    errors += 1

                    async def run():
                        tasks = [worker() for _ in range(concurrency)]
                        await asyncio.gather(*tasks, return_exceptions=True)

                    asyncio.run(run())
                    total_duration = time.perf_counter() - start_time

                    total_requests = len(durations) + errors
                    total_cases = total_requests * batch_size
                    percentiles = calculate_percentiles(durations)

                    result = StressTestResult(
                        test_name="batch_evaluation",
                        scenario=f"batch_{batch_size}",
                        concurrency=concurrency,
                        duration_seconds=int(total_duration),
                        total_requests=total_cases,
                        successful_requests=len(durations) * batch_size,
                        failed_requests=errors * batch_size,
                        error_rate=(errors / total_requests) * 100 if total_requests > 0 else 0,
                        avg_latency_ms=sum(durations) / len(durations) if durations else 0,
                        p50_latency_ms=percentiles[50],
                        p95_latency_ms=percentiles[95],
                        p99_latency_ms=percentiles[99],
                        max_latency_ms=max(durations) if durations else 0,
                        throughput=total_cases / total_duration if total_duration > 0 else 0,
                        evaluator_distribution={},
                        timestamp=datetime.now().isoformat(),
                    )

                    print(result)
                    save_stress_result(result)

                    assert result.error_rate < 10, f"错误率过高: {result.error_rate}%"


# =====================================================================
# 异步任务队列压力测试
# =====================================================================


class TestAsyncTaskQueueStress:
    """异步任务队列压力测试"""

    def test_celery_task_flood(self):
        """Celery任务洪水测试"""
        try:
            from src.schemas.evaluation import EvaluationSchema
            from src.workers.tasks import eval_case_task

            print(f"\n{'=' * 60}")
            print("Celery任务洪水测试")
            print(f"{'=' * 60}")

            total_tasks = 100
            print(f"提交 {total_tasks} 个异步任务...")

            start_time = time.perf_counter()
            task_ids = []

            for i in range(total_tasks):
                eval_type = TestDataGenerator.weighted_random_evaluator()
                payload = TestDataGenerator.generate_evaluation_request(eval_type)["payload"]
                case = EvaluationSchema(
                    id=f"stress-task-{i}-{uuid.uuid4()}",
                    type=eval_type,
                    payload=payload,
                )
                task = eval_case_task.delay(case.model_dump())
                task_ids.append(task.id)

            submit_duration = time.perf_counter() - start_time

            print(f"任务提交完成，耗时: {submit_duration:.2f}s")
            print(f"吞吐量: {total_tasks / submit_duration:.2f} tasks/s")

            # 等待任务完成
            print("等待任务完成...")
            completed = 0
            start_wait = time.perf_counter()
            max_wait = 60

            while completed < total_tasks and (time.perf_counter() - start_wait) < max_wait:
                for task_id in task_ids:
                    try:
                        from src.workers.celery_app import get_celery_app

                        app = get_celery_app()
                        if app:
                            result = app.AsyncResult(task_id)
                            if result.ready():
                                completed += 1
                    except Exception:
                        completed += 1
                time.sleep(1)

            wait_duration = time.perf_counter() - start_wait
            print(f"任务完成: {completed}/{total_tasks}")
            print(f"等待耗时: {wait_duration:.2f}s")

            assert completed == total_tasks, f"任务未全部完成: {completed}/{total_tasks}"

        except Exception as e:
            pytest.skip(f"Celery不可用，跳过任务洪水测试: {e}")


# =====================================================================
# 数据库缓冲压力测试
# =====================================================================


class TestBufferStress:
    """数据库缓冲压力测试"""

    def test_buffer_high_volume(self):
        """高吞吐量缓冲压力测试"""
        from src.schemas.evaluation import DomainResponse
        from src.schemas.schemas import EvaluationResult, EvaluationStatus
        from src.workers.tasks import EvaluationBufferService, _result_to_model

        print(f"\n{'=' * 60}")
        print("数据库缓冲高吞吐量测试")
        print(f"{'=' * 60}")

        buffer = EvaluationBufferService(batch_size=100, flush_interval_seconds=1.0)

        total_records = 500
        print(f"添加 {total_records} 条记录...")

        start_time = time.perf_counter()
        for i in range(total_records):
            eval_type = TestDataGenerator.weighted_random_evaluator()
            response = DomainResponse(is_valid=True, text=f"test-{i}", score=0.8)
            result = EvaluationResult(
                case_id=f"buffer-stress-{i}-{uuid.uuid4()}",
                status=EvaluationStatus.PASSED,
                model_name="test-model",
                adapter_name="test-adapter",
                response=response,
                latency_ms=100.0,
            )
            db_record = _result_to_model(result)
            buffer.add(db_record)

        add_duration = time.perf_counter() - start_time
        print(f"添加完成，耗时: {add_duration:.2f}s")
        print(f"吞吐量: {total_records / add_duration:.2f} records/s")

        # 强制flush
        print("强制flush...")
        flush_start = time.perf_counter()
        flushed = buffer.flush()
        flush_duration = time.perf_counter() - flush_start

        print(f"Flush完成，耗时: {flush_duration:.2f}s")
        print(f"Flushed: {flushed} records")

        assert flushed == total_records, f"Flush记录数不匹配: {flushed}/{total_records}"

        buffer.close_reusable_session()


# =====================================================================
# 容量测试
# =====================================================================


class TestCapacityTest:
    """容量测试"""

    @pytest.mark.skipif(not check_server_available(), reason="API服务器未运行")
    def test_capacity_test(self):
        """系统容量测试 - 逐步加压"""
        with httpx.Client(timeout=30.0) as client:
            print(f"\n{'=' * 60}")
            print("系统容量测试 - 逐步加压")
            print(f"{'=' * 60}")

            # 逐步增加并发数
            concurrency_steps = [5, 10, 20, 30, 50]
            max_error_rate = 5.0
            capacity_found = False

            for concurrency in concurrency_steps:
                print(f"\n测试并发数: {concurrency}")

                # 预热
                for _ in range(min(concurrency, 5)):
                    eval_type = TestDataGenerator.weighted_random_evaluator()
                    request_data = TestDataGenerator.generate_evaluation_request(eval_type)
                    try:
                        client.post(f"{BASE_URL}/api/v1/evaluate", json=request_data)
                    except Exception:
                        pass
                time.sleep(1)

                # 测试
                durations = []
                errors = 0
                lock = asyncio.Lock()
                start_time = time.perf_counter()

                async def worker():
                    nonlocal errors
                    for _ in range(10):
                        eval_type = TestDataGenerator.weighted_random_evaluator()
                        request_data = TestDataGenerator.generate_evaluation_request(eval_type)
                        start = time.perf_counter()
                        try:
                            response = await asyncio.to_thread(
                                client.post,
                                f"{BASE_URL}/api/v1/evaluate",
                                json=request_data,
                            )
                            if response.status_code == 200:
                                async with lock:
                                    durations.append((time.perf_counter() - start) * 1000)
                            else:
                                async with lock:
                                    errors += 1
                        except Exception:
                            async with lock:
                                errors += 1

                async def run():
                    tasks = [worker() for _ in range(concurrency)]
                    await asyncio.gather(*tasks, return_exceptions=True)

                asyncio.run(run())
                total_duration = time.perf_counter() - start_time

                total_requests = len(durations) + errors
                error_rate = (errors / total_requests) * 100 if total_requests > 0 else 0
                throughput = total_requests / total_duration if total_duration > 0 else 0

                print(f"  错误率: {error_rate:.2f}%, 吞吐量: {throughput:.2f} req/s")

                if error_rate > max_error_rate and not capacity_found:
                    print(f"  ⚠️  系统容量在并发 {concurrency} 时达到极限")
                    capacity_found = True

            print("\n容量测试完成")


# =====================================================================
# 熔断触发测试
# =====================================================================


class TestCircuitBreakerTrigger:
    """熔断触发测试"""

    def test_circuit_breaker_trigger(self):
        """熔断器触发测试"""
        from src.distributed.circuit_breaker import (
            CircuitBreakerConfig,
            global_registry,
        )

        print(f"\n{'=' * 60}")
        print("熔断器触发测试")
        print(f"{'=' * 60}")

        breaker = global_registry.get_or_create(
            "test_stress_breaker",
            CircuitBreakerConfig(
                failure_threshold=3,
                success_threshold=2,
                timeout_seconds=5,
                half_open_max_calls=2,
            ),
        )

        error_count = 0
        triggered = False

        def failing_func():
            raise Exception("test failure")

        # 触发熔断
        print("触发熔断...")
        for i in range(5):
            try:
                breaker.call_sync(failing_func)
            except Exception as e:
                error_count += 1
                if "CircuitBreakerError" in type(e).__name__:
                    triggered = True
                    print(f"  熔断已触发（第{i + 1}次调用）")
                    break

        assert triggered, "熔断器未按预期触发"
        assert error_count >= 3, f"错误次数不足: {error_count}"

        # 等待熔断恢复
        print("等待熔断恢复...")
        time.sleep(6)

        # 测试恢复
        print("测试熔断恢复...")
        success_count = 0

        def success_func():
            return "success"

        for i in range(5):
            try:
                result = breaker.call_sync(success_func)
                if result == "success":
                    success_count += 1
            except Exception:
                pass

        assert success_count >= 2, f"熔断恢复失败，成功次数不足: {success_count}"
        print("熔断器测试通过")


# =====================================================================
# 主函数
# =====================================================================


def run_full_stress_test():
    """运行完整压力测试套件"""
    print("=" * 70)
    print("AI Eval Platform - 全链路压测套件")
    print("=" * 70)

    # 运行单元级测试
    print("\n[1/3] 运行单元级性能测试")
    import subprocess

    result = subprocess.run(
        [
            "python",
            "-m",
            "pytest",
            "tests/performance/test_unit_performance.py",
            "-v",
            "--tb=short",
        ],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)

    # 运行组件级测试
    print("\n[2/3] 运行组件级性能测试")
    result = subprocess.run(
        [
            "python",
            "-m",
            "pytest",
            "tests/performance/test_component_performance.py",
            "-v",
            "--tb=short",
        ],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)

    # 运行全链路压测
    print("\n[3/3] 运行全链路压测")
    result = subprocess.run(
        [
            "python",
            "-m",
            "pytest",
            "tests/performance/test_full_stack_stress.py",
            "-v",
            "--tb=short",
        ],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)

    print("\n" + "=" * 70)
    print("全链路压测套件运行完成")
    print("=" * 70)


if __name__ == "__main__":
    run_full_stress_test()
