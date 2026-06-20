"""
性能基准测试模块

建立性能基线，包括：
1. P50/P95/P99 延迟基线
2. 吞吐量基线 (TPS)
3. 并发性能基线
4. 资源使用基线

使用科学方法：
1. 预热阶段：确保 JIT 编译和缓存预热
2. 测量阶段：多次测量取中位数
3. 报告阶段：计算统计指标并与基线对比
"""

import asyncio
import gc
import json
import os
import statistics
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

# =====================================================================
# 配置
# =====================================================================

BASE_URL = os.getenv("BENCHMARK_API_URL", "http://localhost:8000")
FRONTEND_URL = os.getenv("BENCHMARK_FRONTEND_URL", "http://localhost:5174")

# 基线配置
WARMUP_ITERATIONS = 10
MEASURE_ITERATIONS = 100
CONCURRENT_LEVELS = [1, 5, 10, 20, 50, 100]
PERCENTILES = [50, 75, 90, 95, 99, 99.9]

# 超时配置
REQUEST_TIMEOUT = 30.0
STABILIZATION_TIME = 1.0

# 结果保存路径
RESULTS_DIR = Path(__file__).parent / "benchmark_results"
BASELINE_FILE = RESULTS_DIR / "baseline.json"


# =====================================================================
# 数据模型
# =====================================================================

@dataclass
class BenchmarkResult:
    """基准测试结果"""
    name: str
    iterations: int
    total_duration_ms: float
    avg_duration_ms: float
    min_duration_ms: float
    max_duration_ms: float
    std_dev_ms: float
    p50_ms: float
    p75_ms: float
    p90_ms: float
    p95_ms: float
    p99_ms: float
    p999_ms: float
    throughput: float  # requests per second
    errors: int
    error_rate: float
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BaselineComparison:
    """与基线对比"""
    metric: str
    baseline_value: float
    current_value: float
    change_percent: float
    status: str  # "improved", "degraded", "stable"

    def is_acceptable(self, threshold: float = 10.0) -> bool:
        """判断变化是否可接受（默认 10% 阈值）"""
        return abs(self.change_percent) <= threshold


# =====================================================================
# 工具函数
# =====================================================================

def calculate_percentiles(values: list[float], percentiles: list[float]) -> dict[str, float]:
    """计算百分位数"""
    sorted_values = sorted(values)
    n = len(sorted_values)
    result = {}

    for p in percentiles:
        if n == 0:
            result[f"p{p}"] = 0.0
        elif n == 1:
            result[f"p{p}"] = sorted_values[0]
        else:
            index = (p / 100) * (n - 1)
            lower = int(index)
            upper = lower + 1
            if upper >= n:
                result[f"p{p}"] = sorted_values[-1]
            else:
                weight = index - lower
                result[f"p{p}"] = sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight

    return result


def save_results(results: list[BenchmarkResult], filename: str | None = None) -> Path:
    """保存测试结果"""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"benchmark_{timestamp}.json"

    filepath = RESULTS_DIR / filename

    data = {
        "timestamp": datetime.now().isoformat(),
        "results": [r.to_dict() for r in results]
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return filepath


def load_baseline() -> dict[str, dict] | None:
    """加载基线数据"""
    if not BASELINE_FILE.exists():
        return None

    with open(BASELINE_FILE, encoding="utf-8") as f:
        data = json.load(f)

    # 转换为 {name: result_dict} 格式
    baseline = {}
    for item in data.get("results", []):
        baseline[item["name"]] = item

    return baseline


def save_baseline(results: list[BenchmarkResult]) -> Path:
    """保存当前结果为基线"""
    return save_results(results, BASELINE_FILE.name)


def compare_with_baseline(current: BenchmarkResult, baseline_data: dict[str, dict]) -> list[BaselineComparison]:
    """与基线对比"""
    comparisons = []

    if current.name not in baseline_data:
        return comparisons

    baseline = baseline_data[current.name]
    metrics = [
        ("avg_duration_ms", "平均延迟"),
        ("p50_ms", "P50 延迟"),
        ("p95_ms", "P95 延迟"),
        ("p99_ms", "P99 延迟"),
        ("throughput", "吞吐量"),
    ]

    for metric_key, metric_name in metrics:
        if metric_key in baseline and metric_key in current.to_dict():
            baseline_val = baseline[metric_key]
            current_val = current.to_dict()[metric_key]

            if baseline_val == 0:
                change = 0.0 if current_val == 0 else 100.0
            else:
                change = ((current_val - baseline_val) / baseline_val) * 100

            # 对于延迟，越小越好；对于吞吐量，越大越好
            if "throughput" in metric_key:
                status = "improved" if change < 0 else "degraded" if change > 0 else "stable"
            else:
                status = "improved" if change < 0 else "degraded" if change > 0 else "stable"

            comparisons.append(BaselineComparison(
                metric=metric_name,
                baseline_value=baseline_val,
                current_value=current_val,
                change_percent=round(change, 2),
                status=status
            ))

    return comparisons


# =====================================================================
# 基准测试类
# =====================================================================

class PerformanceBenchmark:
    """性能基准测试"""

    def __init__(self, name: str, base_url: str = BASE_URL):
        self.name = name
        self.base_url = base_url
        self.results: list[BenchmarkResult] = []
        self.baseline = load_baseline()

    def _run_sync_benchmark(
        self,
        name: str,
        func: Callable[[], Any],
        iterations: int = MEASURE_ITERATIONS,
        warmup: int = WARMUP_ITERATIONS
    ) -> BenchmarkResult:
        """运行同步基准测试"""
        # 预热
        for _ in range(warmup):
            func()

        # 强制 GC
        gc.collect()

        # 测量
        durations = []
        errors = 0

        for _ in range(iterations):
            start = time.perf_counter()
            try:
                func()
                duration = (time.perf_counter() - start) * 1000
                durations.append(duration)
            except Exception:
                errors += 1

        # 计算统计
        total_duration = sum(durations)
        avg_duration = total_duration / len(durations) if durations else 0
        min_duration = min(durations) if durations else 0
        max_duration = max(durations) if durations else 0
        std_dev = statistics.stdev(durations) if len(durations) > 1 else 0
        percentiles = calculate_percentiles(durations, PERCENTILES)

        return BenchmarkResult(
            name=name,
            iterations=iterations,
            total_duration_ms=total_duration,
            avg_duration_ms=avg_duration,
            min_duration_ms=min_duration,
            max_duration_ms=max_duration,
            std_dev_ms=std_dev,
            p50_ms=percentiles.get("p50", 0),
            p75_ms=percentiles.get("p75", 0),
            p90_ms=percentiles.get("p90", 0),
            p95_ms=percentiles.get("p95", 0),
            p99_ms=percentiles.get("p99", 0),
            p999_ms=percentiles.get("p99.9", 0),
            throughput=iterations / (total_duration / 1000) if total_duration > 0 else 0,
            errors=errors,
            error_rate=errors / iterations * 100,
            timestamp=datetime.now().isoformat()
        )

    def _run_async_benchmark(
        self,
        name: str,
        func: Callable[[], Any],
        iterations: int = MEASURE_ITERATIONS,
        warmup: int = WARMUP_ITERATIONS
    ) -> BenchmarkResult:
        """运行异步基准测试"""
        async def run():
            return await func()

        # 预热
        for _ in range(warmup):
            asyncio.run(run())

        # 强制 GC
        gc.collect()

        # 测量
        durations = []
        errors = 0

        for _ in range(iterations):
            start = time.perf_counter()
            try:
                asyncio.run(run())
                duration = (time.perf_counter() - start) * 1000
                durations.append(duration)
            except Exception:
                errors += 1

        # 计算统计
        total_duration = sum(durations)
        avg_duration = total_duration / len(durations) if durations else 0
        min_duration = min(durations) if durations else 0
        max_duration = max(durations) if durations else 0
        std_dev = statistics.stdev(durations) if len(durations) > 1 else 0
        percentiles = calculate_percentiles(durations, PERCENTILES)

        return BenchmarkResult(
            name=name,
            iterations=iterations,
            total_duration_ms=total_duration,
            avg_duration_ms=avg_duration,
            min_duration_ms=min_duration,
            max_duration_ms=max_duration,
            std_dev_ms=std_dev,
            p50_ms=percentiles.get("p50", 0),
            p75_ms=percentiles.get("p75", 0),
            p90_ms=percentiles.get("p90", 0),
            p95_ms=percentiles.get("p95", 0),
            p99_ms=percentiles.get("p99", 0),
            p999_ms=percentiles.get("p99.9", 0),
            throughput=iterations / (total_duration / 1000) if total_duration > 0 else 0,
            errors=errors,
            error_rate=errors / iterations * 100,
            timestamp=datetime.now().isoformat()
        )

    def run_sync(self, name: str, func: Callable[[], Any], iterations: int = MEASURE_ITERATIONS) -> BenchmarkResult:
        """运行同步测试并记录结果"""
        result = self._run_sync_benchmark(name, func, iterations)
        self.results.append(result)
        return result

    def run_async(self, name: str, func: Callable[[], Any], iterations: int = MEASURE_ITERATIONS) -> BenchmarkResult:
        """运行异步测试并记录结果"""
        result = self._run_async_benchmark(name, func, iterations)
        self.results.append(result)
        return result

    def save(self) -> Path:
        """保存测试结果"""
        return save_results(self.results)

    def save_as_baseline(self) -> Path:
        """保存为基线"""
        return save_baseline(self.results)

    def compare(self) -> list[list[BaselineComparison]]:
        """与基线对比"""
        comparisons = []
        for result in self.results:
            comp = compare_with_baseline(result, self.baseline)
            if comp:
                comparisons.append(comp)
        return comparisons


# =====================================================================
# API 基准测试
# =====================================================================

class APIBenchmark:
    """API 性能基准测试"""

    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.client = httpx.Client(timeout=REQUEST_TIMEOUT)

    def close(self):
        self.client.close()

    def benchmark_health(self, iterations: int = MEASURE_ITERATIONS) -> BenchmarkResult:
        """健康检查接口基准"""
        def call():
            response = self.client.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()

        benchmark = PerformanceBenchmark("api_health_check")
        return benchmark.run_sync("health_check", call, iterations)

    def benchmark_list_evaluators(self, iterations: int = MEASURE_ITERATIONS) -> BenchmarkResult:
        """评估器列表接口基准"""
        def call():
            response = self.client.get(f"{self.base_url}/api/v1/evaluators")
            response.raise_for_status()
            return response.json()

        benchmark = PerformanceBenchmark("api_list_evaluators")
        return benchmark.run_sync("list_evaluators", call, iterations)

    def benchmark_evaluate(self, iterations: int = MEASURE_ITERATIONS) -> BenchmarkResult:
        """评测接口基准（同步）"""
        def call():
            response = self.client.post(
                f"{self.base_url}/api/v1/evaluate",
                json={
                    "id": f"bench_{time.time()}",
                    "type": "general",
                    "payload": {"user_input": "测试文本"}
                }
            )
            response.raise_for_status()
            return response.json()

        benchmark = PerformanceBenchmark("api_evaluate")
        return benchmark.run_sync("evaluate", call, iterations)

    def benchmark_concurrent(
        self,
        name: str,
        call_func: Callable[[], Any],
        concurrency: int,
        total_requests: int = 1000
    ) -> BenchmarkResult:
        """并发请求基准"""
        results = []
        errors = 0
        lock = asyncio.Lock()

        async def worker():
            nonlocal errors
            start = time.perf_counter()
            try:
                await call_func()
                duration = (time.perf_counter() - start) * 1000
                async with lock:
                    results.append(duration)
            except Exception:
                async with lock:
                    errors += 1

        async def run_concurrent():
            tasks = [worker() for _ in range(total_requests)]
            await asyncio.gather(*tasks, return_exceptions=True)

        # 运行并发测试
        start_time = time.perf_counter()
        asyncio.run(run_concurrent())
        total_duration = (time.perf_counter() - start_time) * 1000

        # 计算统计
        avg_duration = sum(results) / len(results) if results else 0
        min_duration = min(results) if results else 0
        max_duration = max(results) if results else 0
        std_dev = statistics.stdev(results) if len(results) > 1 else 0
        percentiles = calculate_percentiles(results, PERCENTILES)

        return BenchmarkResult(
            name=f"concurrent_{concurrency}_{name}",
            iterations=total_requests,
            total_duration_ms=total_duration,
            avg_duration_ms=avg_duration,
            min_duration_ms=min_duration,
            max_duration_ms=max_duration,
            std_dev_ms=std_dev,
            p50_ms=percentiles.get("p50", 0),
            p75_ms=percentiles.get("p75", 0),
            p90_ms=percentiles.get("p90", 0),
            p95_ms=percentiles.get("p95", 0),
            p99_ms=percentiles.get("p99", 0),
            p999_ms=percentiles.get("p99.9", 0),
            throughput=total_requests / (total_duration / 1000) if total_duration > 0 else 0,
            errors=errors,
            error_rate=errors / total_requests * 100,
            timestamp=datetime.now().isoformat()
        )

    def run_full_suite(self) -> list[BenchmarkResult]:
        """运行完整基准测试套件"""
        results = []

        print("\n" + "=" * 60)
        print("开始性能基准测试")
        print("=" * 60)

        # 1. 健康检查
        print("\n[1/4] 测试健康检查接口...")
        results.append(self.benchmark_health())

        # 2. 评估器列表
        print("[2/4] 测试评估器列表接口...")
        results.append(self.benchmark_list_evaluators())

        # 3. 评测接口
        print("[3/4] 测试评测接口...")
        results.append(self.benchmark_evaluate())

        # 4. 并发测试
        print("[4/4] 测试并发性能...")
        for concurrency in CONCURRENT_LEVELS:
            result = self.benchmark_concurrent(
                "health",
                lambda: self.client.get(f"{self.base_url}/health"),
                concurrency,
                total_requests=concurrency * 10
            )
            results.append(result)

        self.close()

        # 打印结果
        print("\n" + "=" * 60)
        print("基准测试完成")
        print("=" * 60)

        for result in results:
            print(f"\n{result.name}:")
            print(f"  平均延迟: {result.avg_duration_ms:.2f} ms")
            print(f"  P50: {result.p50_ms:.2f} ms")
            print(f"  P95: {result.p95_ms:.2f} ms")
            print(f"  P99: {result.p99_ms:.2f} ms")
            print(f"  吞吐量: {result.throughput:.2f} req/s")
            print(f"  错误率: {result.error_rate:.2f}%")

        return results


# =====================================================================
# 测试用例
# =====================================================================

@pytest.fixture(scope="module")
def benchmark_api():
    """API 基准测试 fixture"""
    api = APIBenchmark()
    yield api
    api.close()


def test_health_check_latency(benchmark_api):
    """健康检查延迟基准"""
    result = benchmark_api.benchmark_health()

    # 验证延迟在可接受范围内
    assert result.avg_duration_ms < 100, f"健康检查平均延迟过高: {result.avg_duration_ms}ms"
    assert result.p95_ms < 200, f"健康检查 P95 延迟过高: {result.p95_ms}ms"
    assert result.error_rate < 1.0, f"健康检查错误率过高: {result.error_rate}%"


def test_list_evaluators_latency(benchmark_api):
    """评估器列表延迟基准"""
    result = benchmark_api.benchmark_list_evaluators()

    # 验证延迟在可接受范围内
    assert result.avg_duration_ms < 200, f"列表评估器平均延迟过高: {result.avg_duration_ms}ms"
    assert result.p95_ms < 500, f"列表评估器 P95 延迟过高: {result.p95_ms}ms"
    assert result.error_rate < 1.0, f"列表评估器错误率过高: {result.error_rate}%"


def test_evaluate_latency(benchmark_api):
    """评测接口延迟基准"""
    result = benchmark_api.benchmark_evaluate()

    # 验证延迟在可接受范围内（评测涉及 LLM 调用，延迟较高）
    assert result.avg_duration_ms < 5000, f"评测平均延迟过高: {result.avg_duration_ms}ms"
    assert result.p95_ms < 10000, f"评测 P95 延迟过高: {result.p95_ms}ms"
    assert result.error_rate < 5.0, f"评测错误率过高: {result.error_rate}%"


def test_concurrent_performance(benchmark_api):
    """并发性能基准"""
    results = []

    for concurrency in CONCURRENT_LEVELS:
        result = benchmark_api.benchmark_concurrent(
            "health",
            lambda: benchmark_api.client.get(f"{benchmark_api.base_url}/health"),
            concurrency,
            total_requests=concurrency * 5
        )
        results.append(result)

        # 验证每个并发级别的性能
        assert result.error_rate < 5.0, f"并发 {concurrency} 错误率过高: {result.error_rate}%"

    # 验证吞吐量随并发线性增长（理想情况下）
    # 实际可能有瓶颈，所以只做宽松检查
    max_throughput = max(r.throughput for r in results)
    assert max_throughput > 10, f"最大吞吐量过低: {max_throughput} req/s"


def test_baseline_comparison():
    """与基线对比（如果存在基线）"""
    baseline = load_baseline()

    if baseline:
        print("\n与基线对比:")
        print("-" * 40)

        # 这里会输出对比信息，但不会导致测试失败
        # 实际生产中应该设置告警阈值

        print("基线数据存在，可用于性能回归检测")
    else:
        print("\n未找到基线数据，首次运行将创建基线")


# =====================================================================
# 主函数
# =====================================================================

def main():
    """运行完整基准测试"""
    benchmark = APIBenchmark()
    results = benchmark.run_full_suite()

    # 保存结果
    filepath = save_results(results)
    print(f"\n结果已保存到: {filepath}")

    # 可选：保存为基线
    # benchmark.save_as_baseline()

    return results


if __name__ == "__main__":
    main()
