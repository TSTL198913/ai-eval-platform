"""
性能压测工具

用于验证 P99 延迟是否满足要求。
"""

import asyncio
import statistics
import time
from dataclasses import dataclass

import httpx


@dataclass
class LoadTestConfig:
    """负载测试配置"""

    url: str
    method: str = "POST"
    headers: dict | None = None
    json_data: dict | None = None
    concurrency: int = 10  # 并发数
    total_requests: int = 1000  # 总请求数
    timeout: float = 30.0  # 请求超时


@dataclass
class LoadTestResult:
    """负载测试结果"""

    total_requests: int
    success_count: int
    error_count: int
    total_duration_ms: float
    latencies: list[float]
    errors: list[str]

    @property
    def success_rate(self) -> float:
        return self.success_count / self.total_requests * 100

    @property
    def avg_latency_ms(self) -> float:
        return statistics.mean(self.latencies) if self.latencies else 0

    @property
    def p50_latency_ms(self) -> float:
        return statistics.median(self.latencies) if self.latencies else 0

    @property
    def p95_latency_ms(self) -> float:
        if not self.latencies:
            return 0
        sorted_latencies = sorted(self.latencies)
        idx = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[idx]

    @property
    def p99_latency_ms(self) -> float:
        if not self.latencies:
            return 0
        sorted_latencies = sorted(self.latencies)
        idx = int(len(sorted_latencies) * 0.99)
        return sorted_latencies[idx]

    @property
    def max_latency_ms(self) -> float:
        return max(self.latencies) if self.latencies else 0

    @property
    def min_latency_ms(self) -> float:
        return min(self.latencies) if self.latencies else 0

    def to_dict(self) -> dict:
        return {
            "total_requests": self.total_requests,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "success_rate": f"{self.success_rate:.2f}%",
            "total_duration_ms": f"{self.total_duration_ms:.2f}",
            "latency_ms": {
                "min": f"{self.min_latency_ms:.2f}",
                "avg": f"{self.avg_latency_ms:.2f}",
                "p50": f"{self.p50_latency_ms:.2f}",
                "p95": f"{self.p95_latency_ms:.2f}",
                "p99": f"{self.p99_latency_ms:.2f}",
                "max": f"{self.max_latency_ms:.2f}",
            },
        }


async def make_request(
    client: httpx.AsyncClient,
    config: LoadTestConfig,
) -> tuple[float, bool, str]:
    """发送单个请求"""
    start_time = time.time()
    error = ""

    try:
        if config.method == "POST":
            response = await client.post(
                config.url,
                json=config.json_data,
                headers=config.headers,
                timeout=config.timeout,
            )
        else:
            response = await client.get(
                config.url,
                headers=config.headers,
                timeout=config.timeout,
            )

        success = response.status_code < 400
        if not success:
            error = f"HTTP {response.status_code}"

    except httpx.TimeoutException:
        success = False
        error = "Timeout"
    except Exception as e:
        success = False
        error = str(e)

    latency_ms = (time.time() - start_time) * 1000
    return latency_ms, success, error


async def run_load_test(config: LoadTestConfig) -> LoadTestResult:
    """运行负载测试"""
    print(f"Starting load test: {config.concurrency} concurrent, {config.total_requests} total")

    latencies = []
    errors = []
    success_count = 0
    error_count = 0

    # 创建信号量控制并发
    semaphore = asyncio.Semaphore(config.concurrency)

    async with httpx.AsyncClient() as client:

        async def bounded_request():
            nonlocal success_count, error_count
            async with semaphore:
                latency, success, error = await make_request(client, config)
                latencies.append(latency)
                if success:
                    success_count += 1
                else:
                    error_count += 1
                    errors.append(error)

        # 创建所有请求
        start_time = time.time()
        tasks = [bounded_request() for _ in range(config.total_requests)]

        # 并发执行
        await asyncio.gather(*tasks)
        total_duration_ms = (time.time() - start_time) * 1000

    return LoadTestResult(
        total_requests=config.total_requests,
        success_count=success_count,
        error_count=error_count,
        total_duration_ms=total_duration_ms,
        latencies=latencies,
        errors=errors,
    )


def verify_performance(
    result: LoadTestResult,
    targets: dict[str, float],
) -> dict[str, bool]:
    """验证性能是否达标"""
    checks = {
        "p50_ok": result.p50_latency_ms <= targets.get("p50", 100),
        "p95_ok": result.p95_latency_ms <= targets.get("p95", 300),
        "p99_ok": result.p99_latency_ms <= targets.get("p99", 500),
        "success_rate_ok": result.success_rate >= targets.get("min_success_rate", 99),
    }
    return checks


def print_results(result: LoadTestResult, targets: dict | None = None):
    """打印测试结果"""
    print("\n" + "=" * 60)
    print("Load Test Results")
    print("=" * 60)

    print(f"\nTotal Requests: {result.total_requests}")
    print(f"Success: {result.success_count} ({result.success_rate:.2f}%)")
    print(f"Errors: {result.error_count}")
    print(f"Duration: {result.total_duration_ms:.2f}ms")

    print("\nLatency Statistics:")
    print(f"  Min:     {result.min_latency_ms:8.2f}ms")
    print(f"  Avg:     {result.avg_latency_ms:8.2f}ms")
    print(f"  P50:     {result.p50_latency_ms:8.2f}ms")
    print(f"  P95:     {result.p95_latency_ms:8.2f}ms")
    print(f"  P99:     {result.p99_latency_ms:8.2f}ms")
    print(f"  Max:     {result.max_latency_ms:8.2f}ms")

    if targets:
        print("\nPerformance Targets:")
        print(
            f"  P50 Target:    {targets.get('p50', 100):8.2f}ms  {'✓' if result.p50_latency_ms <= targets.get('p50', 100) else '✗'}"
        )
        print(
            f"  P95 Target:    {targets.get('p95', 300):8.2f}ms  {'✓' if result.p95_latency_ms <= targets.get('p95', 300) else '✗'}"
        )
        print(
            f"  P99 Target:    {targets.get('p99', 500):8.2f}ms  {'✓' if result.p99_latency_ms <= targets.get('p99', 500) else '✗'}"
        )
        print(
            f"  Success Rate:  {targets.get('min_success_rate', 99):8.2f}%  {'✓' if result.success_rate >= targets.get('min_success_rate', 99) else '✗'}"
        )

    # 显示错误分布
    if result.errors:
        print("\nError Distribution:")
        error_counts = {}
        for error in result.errors:
            error_counts[error] = error_counts.get(error, 0) + 1
        for error, count in sorted(error_counts.items(), key=lambda x: -x[1])[:5]:
            print(f"  {error}: {count}")

    print("\n" + "=" * 60)


async def run_benchmark_suite():
    """运行基准测试套件"""
    # 测试配置
    configs = [
        LoadTestConfig(
            url="http://localhost:8000/health",
            method="GET",
            concurrency=10,
            total_requests=500,
        ),
        LoadTestConfig(
            url="http://localhost:8000/v1/evaluate",
            method="POST",
            json_data={
                "model": "gpt-4",
                "dataset": "mmlu",
                "metrics": ["accuracy"],
            },
            concurrency=10,
            total_requests=500,
        ),
    ]

    # 性能目标
    targets = {
        "p50": 50,
        "p95": 100,
        "p99": 200,
        "min_success_rate": 99.9,
    }

    print("AI Eval Platform Performance Benchmark")
    print("=" * 60)

    all_passed = True
    for config in configs:
        print(f"\n\nTesting: {config.method} {config.url}")
        result = await run_load_test(config)
        print_results(result, targets)

        checks = verify_performance(result, targets)
        if not all(checks.values()):
            all_passed = False

    print("\n\n" + "=" * 60)
    if all_passed:
        print("✓ All benchmarks passed!")
    else:
        print("✗ Some benchmarks failed!")
    print("=" * 60)

    return all_passed


# 简单的同步测试函数
def simple_latency_test(url: str, count: int = 100) -> dict:
    """简单延迟测试"""
    latencies = []

    for _ in range(count):
        start = time.time()
        try:
            import urllib.request

            urllib.request.urlopen(url, timeout=5)
            latency = (time.time() - start) * 1000
            latencies.append(latency)
        except Exception:
            pass

    if not latencies:
        return {"error": "No successful requests"}

    return {
        "count": len(latencies),
        "min": min(latencies),
        "avg": sum(latencies) / len(latencies),
        "max": max(latencies),
        "p95": sorted(latencies)[int(len(latencies) * 0.95)],
        "p99": sorted(latencies)[int(len(latencies) * 0.99)],
    }


if __name__ == "__main__":
    # 运行基准测试
    asyncio.run(run_benchmark_suite())
