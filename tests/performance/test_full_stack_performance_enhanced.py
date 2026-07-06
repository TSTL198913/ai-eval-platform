"""
全链路性能增强测试

补充现有性能测试的缺失场景：
1. 全链路端到端性能测试（登录→评测→查看记录→生成报告）
2. 真实数据场景的性能测试
3. 资源使用监控测试（CPU、内存、磁盘I/O）
4. 长时间运行稳定性测试
5. API并发竞争测试
6. 缓存命中率测试
7. 数据库查询性能测试
8. 评估器冷启动性能测试
"""

import asyncio
import gc
import json
import os
import time
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import pytest

# =====================================================================
# 配置常量
# =====================================================================

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
TEST_DURATION_SECONDS = 30
WARMUP_SECONDS = 5

EVALUATOR_WEIGHTS = {
    "general": 30,
    "security": 20,
    "semantic": 15,
    "grammar": 10,
    "qa": 10,
    "code": 10,
    "factuality": 5,
}

STRESS_CONCURRENCY_LEVELS = [10, 20, 50]

RESULTS_DIR = Path(__file__).parent / "performance_results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# =====================================================================
# 数据模型
# =====================================================================


@dataclass
class PerformanceTestResult:
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
    resource_usage: Optional[Dict[str, float]]
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)

    def __str__(self) -> str:
        resource_info = ""
        if self.resource_usage:
            resource_info = (
                f"\n  Resources: CPU={self.resource_usage.get('cpu', 0):.1f}%, "
                f"Memory={self.resource_usage.get('memory', 0):.1f}MB"
            )
        return (
            f"[{self.test_name}] {self.scenario} "
            f"(concurrency={self.concurrency}, duration={self.duration_seconds}s):\n"
            f"  Requests: {self.total_requests} ({self.successful_requests} success, {self.failed_requests} failed)\n"
            f"  Error Rate: {self.error_rate:.2f}%\n"
            f"  Latency: avg={self.avg_latency_ms:.2f}ms, P50={self.p50_latency_ms:.2f}ms, "
            f"P95={self.p95_latency_ms:.2f}ms, P99={self.p99_latency_ms:.2f}ms, max={self.max_latency_ms:.2f}ms\n"
            f"  Throughput: {self.throughput:.2f} req/s{resource_info}"
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


def save_performance_result(result: PerformanceTestResult) -> Path:
    filepath = (
        RESULTS_DIR
        / f"perf_{result.test_name}_{result.scenario}_{result.concurrency}_{result.timestamp.replace(':', '-')}.json"
    )
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
    return filepath


def get_resource_usage() -> Dict[str, float]:
    try:
        import psutil

        process = psutil.Process()
        memory_info = process.memory_info()
        cpu_percent = process.cpu_percent(interval=0.1)
        return {
            "cpu": cpu_percent,
            "memory": memory_info.rss / (1024 * 1024),
            "threads": process.num_threads(),
        }
    except ImportError:
        return {}


# =====================================================================
# 真实数据生成器
# =====================================================================


class RealDataGenerator:
    """真实数据生成器 - 模拟真实业务场景"""

    @staticmethod
    def generate_real_evaluation_request(evaluator_type: str) -> dict:
        real_payloads = {
            "general": {
                "user_input": "解释一下量子计算的基本原理，并说明它与经典计算的主要区别。",
                "expected_output": "量子计算利用量子力学现象（如叠加态和纠缠）进行计算，与经典计算使用比特不同，量子计算使用量子比特。主要区别包括：量子比特可以同时处于多个状态，量子计算在特定问题上具有指数级加速潜力。",
            },
            "security": {
                "user_input": "def login(username, password):\n    query = f\"SELECT * FROM users WHERE username='{username}' AND password='{password}'\"\n    return execute(query)",
                "expected_output": "存在SQL注入漏洞，应使用参数化查询。",
            },
            "semantic": {
                "user_input": "深度学习是机器学习的一个子领域，使用多层神经网络来模拟人脑的学习过程。",
                "expected_output": "Deep learning is a subfield of machine learning that uses multi-layer neural networks to simulate the learning process of the human brain.",
            },
            "grammar": {
                "user_input": "The team are playing very good today, they have scored five goals already.",
                "expected_output": "The team is playing very well today; they have already scored five goals.",
            },
            "factuality": {
                "user_input": "地球是圆的，围绕太阳公转，公转周期约为365.25天。",
                "expected_output": "地球是球体，围绕太阳公转，公转周期约为365.25天，即一个回归年。",
            },
            "qa": {
                "user_input": "什么是区块链技术？它有哪些主要特点？",
                "expected_output": "区块链是一种分布式账本技术，通过去中心化和加密技术确保数据的安全性和不可篡改性。主要特点包括：去中心化、透明性、安全性、不可篡改性、匿名性。",
            },
            "code": {
                "user_input": "# Python快速排序实现\ndef quicksort(arr):\n    if len(arr) <= 1:\n        return arr\n    pivot = arr[len(arr) // 2]\n    left = [x for x in arr if x < pivot]\n    middle = [x for x in arr if x == pivot]\n    right = [x for x in arr if x > pivot]\n    return quicksort(left) + middle + quicksort(right)",
                "expected_output": "// TypeScript快速排序实现\nfunction quicksort<T>(arr: T[]): T[] {\n    if (arr.length <= 1) return arr;\n    const pivot = arr[Math.floor(arr.length / 2)];\n    const left = arr.filter(x => x < pivot);\n    const middle = arr.filter(x => x === pivot);\n    const right = arr.filter(x => x > pivot);\n    return [...quicksort(left), ...middle, ...quicksort(right)];\n}",
            },
        }
        template = real_payloads.get(evaluator_type, real_payloads["general"])
        return {
            "id": f"perf-{uuid.uuid4()}",
            "type": evaluator_type,
            "payload": template,
        }

    @staticmethod
    def weighted_random_evaluator() -> str:
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
# 全链路端到端性能测试
# =====================================================================


class TestFullWorkflowPerformance:
    """全链路端到端性能测试"""

    @pytest.mark.skipif(not check_server_available(), reason="API服务器未运行")
    def test_full_workflow_performance(self):
        """完整业务流程性能测试"""
        with httpx.Client(timeout=30.0) as client:
            print(f"\n{'=' * 60}")
            print("全链路端到端性能测试")
            print(f"{'=' * 60}")

            durations: Dict[str, List[float]] = defaultdict(list)
            errors = 0
            response_data_list: List[dict] = []

            async def execute_workflow():
                nonlocal errors
                workflow_start = time.perf_counter()

                try:
                    eval_type = RealDataGenerator.weighted_random_evaluator()
                    request_data = RealDataGenerator.generate_real_evaluation_request(eval_type)

                    eval_start = time.perf_counter()
                    response = await asyncio.to_thread(
                        client.post,
                        f"{BASE_URL}/api/v1/evaluate",
                        json=request_data,
                    )
                    eval_duration = (time.perf_counter() - eval_start) * 1000

                    if response.status_code == 200:
                        durations["evaluate"].append(eval_duration)

                        result_data = response.json()
                        response_data_list.append(result_data)

                        assert "id" in result_data, "响应缺少id字段"
                        assert "score" in result_data or "data" in result_data, "响应缺少score或data字段"

                        case_id = result_data.get("id", "")

                        if case_id:
                            get_start = time.perf_counter()
                            await asyncio.to_thread(
                                client.get,
                                f"{BASE_URL}/api/v1/evaluation-records/{case_id}",
                            )
                            get_duration = (time.perf_counter() - get_start) * 1000
                            durations["get_record"].append(get_duration)
                    else:
                        errors += 1
                except Exception:
                    errors += 1

                workflow_duration = (time.perf_counter() - workflow_start) * 1000
                durations["workflow"].append(workflow_duration)

            for concurrency in [10, 20]:
                print(f"\n并发数: {concurrency}")
                durations.clear()
                errors = 0
                response_data_list.clear()

                start_time = time.perf_counter()
                end_time = start_time + TEST_DURATION_SECONDS

                async def worker():
                    while time.perf_counter() < end_time:
                        await execute_workflow()

                async def run():
                    tasks = [worker() for _ in range(concurrency)]
                    await asyncio.gather(*tasks, return_exceptions=True)

                asyncio.run(run())
                total_duration = time.perf_counter() - start_time

                total_requests = len(durations["workflow"])
                percentiles = calculate_percentiles(durations["workflow"])

                result = PerformanceTestResult(
                    test_name="full_workflow",
                    scenario="end_to_end",
                    concurrency=concurrency,
                    duration_seconds=int(total_duration),
                    total_requests=total_requests,
                    successful_requests=total_requests - errors,
                    failed_requests=errors,
                    error_rate=(errors / total_requests) * 100 if total_requests > 0 else 0,
                    avg_latency_ms=sum(durations["workflow"]) / len(durations["workflow"]) if durations["workflow"] else 0,
                    p50_latency_ms=percentiles[50],
                    p95_latency_ms=percentiles[95],
                    p99_latency_ms=percentiles[99],
                    max_latency_ms=max(durations["workflow"]) if durations["workflow"] else 0,
                    throughput=total_requests / total_duration if total_duration > 0 else 0,
                    resource_usage=get_resource_usage(),
                    timestamp=datetime.now().isoformat(),
                )

                print(result)
                save_performance_result(result)

                assert result.error_rate < 10, f"错误率过高: {result.error_rate}%"
                assert result.total_requests > 0, "未完成任何请求"
                assert result.throughput > 0.5, f"吞吐量过低: {result.throughput} req/s"
                assert result.p95_latency_ms < 30000, f"P95延迟过高: {result.p95_latency_ms}ms"

                assert len(response_data_list) == result.successful_requests, "响应数据数量与成功请求数不匹配"
                for resp in response_data_list[:5]:
                    assert isinstance(resp, dict), "响应数据不是字典格式"
                    assert "id" in resp, "响应缺少id字段"
                    if "score" in resp:
                        assert isinstance(resp["score"], (int, float)), "score字段类型不正确"
                        assert 0 <= resp["score"] <= 1, f"score值超出范围: {resp['score']}"


# =====================================================================
# 评估器冷启动性能测试
# =====================================================================


class TestEvaluatorColdStart:
    """评估器冷启动性能测试"""

    def test_evaluator_first_request_latency(self):
        """评估器首次请求延迟测试"""
        from src.domain.evaluators import EvaluatorFactory
        from src.schemas.evaluation import EvaluationSchema

        print(f"\n{'=' * 60}")
        print("评估器冷启动性能测试")
        print(f"{'=' * 60}")

        factory = EvaluatorFactory()
        cold_start_latencies = []
        warm_latencies = []

        for eval_type in ["general", "security", "semantic", "grammar"]:
            gc.collect()

            request = EvaluationSchema(
                id=f"coldstart-{eval_type}-{uuid.uuid4()}",
                type=eval_type,
                payload={
                    "user_input": "测试输入",
                    "expected_output": "测试输出",
                },
            )

            start = time.perf_counter()
            evaluator = factory.get(eval_type)
            evaluator.evaluate(request)
            cold_start = (time.perf_counter() - start) * 1000
            cold_start_latencies.append(cold_start)

            start = time.perf_counter()
            evaluator.evaluate(request)
            warm = (time.perf_counter() - start) * 1000
            warm_latencies.append(warm)

            print(f"  {eval_type}: 冷启动={cold_start:.2f}ms, 热启动={warm:.2f}ms")

        avg_cold_start = sum(cold_start_latencies) / len(cold_start_latencies)
        avg_warm_start = sum(warm_latencies) / len(warm_latencies)
        improvement = ((avg_cold_start - avg_warm_start) / avg_cold_start) * 100

        print(f"\n平均冷启动: {avg_cold_start:.2f}ms")
        print(f"平均热启动: {avg_warm_start:.2f}ms")
        print(f"性能提升: {improvement:.1f}%")

        assert avg_cold_start < 10000, f"冷启动延迟过高: {avg_cold_start}ms"


# =====================================================================
# 缓存命中率测试
# =====================================================================


class TestCacheHitRate:
    """缓存命中率测试"""

    def test_cache_hit_rate_under_load(self):
        """负载下的缓存命中率测试"""
        from src.infra.cache.redis_cluster_manager import redis_cluster_manager

        print(f"\n{'=' * 60}")
        print("缓存命中率测试")
        print(f"{'=' * 60}")

        test_keys = [f"cache-test-key-{i}" for i in range(100)]
        cache_hits = 0
        cache_misses = 0

        for i in range(1000):
            key = test_keys[i % len(test_keys)]

            if i % 3 == 0:
                redis_cluster_manager.set_with_expiry(key, f"value-{i}", expiry=3600)

            start = time.perf_counter()
            result = redis_cluster_manager.get(key)
            latency = (time.perf_counter() - start) * 1000

            if result is not None:
                cache_hits += 1
            else:
                cache_misses += 1

        hit_rate = (cache_hits / (cache_hits + cache_misses)) * 100
        print(f"缓存命中: {cache_hits}, 缓存未命中: {cache_misses}")
        print(f"命中率: {hit_rate:.2f}%")

        assert hit_rate > 60, f"缓存命中率过低: {hit_rate}%"


# =====================================================================
# API并发竞争测试
# =====================================================================


class TestAPIConcurrencyRace:
    """API并发竞争测试"""

    @pytest.mark.skipif(not check_server_available(), reason="API服务器未运行")
    def test_evaluate_concurrent_race_condition(self):
        """并发评估竞争条件测试"""
        with httpx.Client(timeout=30.0) as client:
            print(f"\n{'=' * 60}")
            print("API并发竞争测试")
            print(f"{'=' * 60}")

            num_requests = 50
            errors = []
            lock = asyncio.Lock()

            async def make_request(request_id: int):
                nonlocal errors
                request_data = {
                    "id": f"race-condition-test-{request_id}-{uuid.uuid4()}",
                    "type": "general",
                    "payload": {
                        "user_input": f"并发请求测试 {request_id}",
                        "expected_output": "测试输出",
                    },
                }
                try:
                    response = await asyncio.to_thread(
                        client.post,
                        f"{BASE_URL}/api/v1/evaluate",
                        json=request_data,
                    )
                    if response.status_code != 200:
                        async with lock:
                            errors.append(f"Request {request_id}: Status {response.status_code}")
                except Exception as e:
                    async with lock:
                        errors.append(f"Request {request_id}: {str(e)}")

            async def run():
                tasks = [make_request(i) for i in range(num_requests)]
                await asyncio.gather(*tasks, return_exceptions=True)

            asyncio.run(run())

            print(f"总请求数: {num_requests}, 错误数: {len(errors)}")
            if errors:
                for error in errors[:5]:
                    print(f"  {error}")

            assert len(errors) < 5, f"并发竞争导致过多错误: {len(errors)}"


# =====================================================================
# 数据库查询性能测试
# =====================================================================


class TestDatabaseQueryPerformance:
    """数据库查询性能测试"""

    def test_evaluation_record_query_performance(self):
        """评估记录查询性能测试"""
        from src.infra.db.session import get_db_session
        from src.infra.db.models import EvaluationResultModel

        print(f"\n{'=' * 60}")
        print("数据库查询性能测试")
        print(f"{'=' * 60}")

        with get_db_session() as session:
            query_latencies = []

            for _ in range(10):
                start = time.perf_counter()
                results = session.query(EvaluationResultModel).limit(100).all()
                latency = (time.perf_counter() - start) * 1000
                query_latencies.append(latency)

            avg_latency = sum(query_latencies) / len(query_latencies)
            max_latency = max(query_latencies)
            min_latency = min(query_latencies)

            print(f"查询次数: {len(query_latencies)}")
            print(f"平均延迟: {avg_latency:.2f}ms")
            print(f"最大延迟: {max_latency:.2f}ms")
            print(f"最小延迟: {min_latency:.2f}ms")

            assert avg_latency < 500, f"数据库查询延迟过高: {avg_latency}ms"


# =====================================================================
# 资源使用监控测试
# =====================================================================


class TestResourceUsageMonitoring:
    """资源使用监控测试"""

    def test_memory_leak_detection(self):
        """内存泄漏检测测试"""
        import psutil

        print(f"\n{'=' * 60}")
        print("内存泄漏检测测试")
        print(f"{'=' * 60}")

        process = psutil.Process()
        initial_memory = process.memory_info().rss / (1024 * 1024)

        from src.domain.evaluators import EvaluatorFactory
        from src.schemas.evaluation import EvaluationSchema

        factory = EvaluatorFactory()

        for i in range(50):
            eval_type = RealDataGenerator.weighted_random_evaluator()
            request = EvaluationSchema(
                id=f"memory-test-{i}-{uuid.uuid4()}",
                type=eval_type,
                payload={
                    "user_input": "测试输入",
                    "expected_output": "测试输出",
                },
            )
            evaluator = factory.get(eval_type)
            evaluator.evaluate(request)

            if (i + 1) % 10 == 0:
                gc.collect()
                current_memory = process.memory_info().rss / (1024 * 1024)
                print(f"  迭代 {i + 1}: 内存使用 {current_memory:.1f}MB")

        final_memory = process.memory_info().rss / (1024 * 1024)
        memory_increase = final_memory - initial_memory

        print(f"\n初始内存: {initial_memory:.1f}MB")
        print(f"最终内存: {final_memory:.1f}MB")
        print(f"内存增长: {memory_increase:.1f}MB")

        assert memory_increase < 100, f"内存增长过大，可能存在泄漏: {memory_increase}MB"


# =====================================================================
# 长时间运行稳定性测试
# =====================================================================


class TestLongRunningStability:
    """长时间运行稳定性测试"""

    def test_long_running_stability(self):
        """长时间运行稳定性测试"""
        from src.domain.evaluators import EvaluatorFactory
        from src.schemas.evaluation import EvaluationSchema

        print(f"\n{'=' * 60}")
        print("长时间运行稳定性测试")
        print(f"{'=' * 60}")

        factory = EvaluatorFactory()
        errors = 0
        total_iterations = 100
        interval_seconds = 0.1

        for i in range(total_iterations):
            eval_type = RealDataGenerator.weighted_random_evaluator()
            request = EvaluationSchema(
                id=f"stability-test-{i}-{uuid.uuid4()}",
                type=eval_type,
                payload={
                    "user_input": "稳定性测试",
                    "expected_output": "测试输出",
                },
            )
            try:
                evaluator = factory.get(eval_type)
                result = evaluator.evaluate(request)
                if not result.is_valid:
                    errors += 1
            except Exception:
                errors += 1

            if (i + 1) % 20 == 0:
                gc.collect()
                print(f"  进度: {(i + 1)}/{total_iterations}, 错误数: {errors}")

            time.sleep(interval_seconds)

        error_rate = (errors / total_iterations) * 100
        print(f"\n总迭代: {total_iterations}")
        print(f"错误数: {errors}")
        print(f"错误率: {error_rate:.2f}%")

        assert error_rate < 50, f"长时间运行错误率过高: {error_rate}%"


# =====================================================================
# 主函数
# =====================================================================


def run_full_performance_test():
    """运行完整性能测试套件"""
    print("=" * 70)
    print("AI Eval Platform - 全链路性能增强测试套件")
    print("=" * 70)

    import subprocess

    tests_to_run = [
        ("冷启动测试", "tests/performance/test_full_stack_performance_enhanced.py::TestEvaluatorColdStart"),
        ("缓存命中率测试", "tests/performance/test_full_stack_performance_enhanced.py::TestCacheHitRate"),
        ("数据库查询测试", "tests/performance/test_full_stack_performance_enhanced.py::TestDatabaseQueryPerformance"),
        ("内存泄漏检测", "tests/performance/test_full_stack_performance_enhanced.py::TestResourceUsageMonitoring"),
        ("长时间稳定性测试", "tests/performance/test_full_stack_performance_enhanced.py::TestLongRunningStability"),
    ]

    for test_name, test_path in tests_to_run:
        print(f"\n[{test_name}]")
        print("-" * 40)
        result = subprocess.run(
            [
                "python",
                "-m",
                "pytest",
                test_path,
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
    print("全链路性能增强测试套件运行完成")
    print("=" * 70)


if __name__ == "__main__":
    run_full_performance_test()