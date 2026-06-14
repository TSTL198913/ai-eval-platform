"""
性能验证脚本

验证 P99 延迟是否 < 100ms
"""

import asyncio
import statistics
import time
from dataclasses import dataclass

import httpx


@dataclass
class PerfTestConfig:
    """性能测试配置"""

    url: str
    name: str
    method: str = "POST"
    headers: dict | None = None
    json_data: dict | None = None
    warmup_requests: int = 50
    test_requests: int = 500
    concurrent: int = 10


@dataclass
class PerfResult:
    """性能测试结果"""

    name: str
    total: int
    success: int
    errors: int
    latencies: list[float]
    p50: float
    p95: float
    p99: float
    avg: float
    min: float
    max: float

    def passed(self, target_p99: float) -> bool:
        return self.p99 <= target_p99 and self.errors / self.total < 0.01


async def test_endpoint(config: PerfTestConfig) -> PerfResult:
    """测试单个端点"""
    print(f"\n{'='*60}")
    print(f"Testing: {config.name}")
    print(f"{'='*60}")

    latencies = []
    errors = []
    success = 0

    async with httpx.AsyncClient(timeout=30.0) as client:

        async def make_request():
            nonlocal success
            start = time.time()
            try:
                if config.method == "POST":
                    r = await client.post(config.url, json=config.json_data, headers=config.headers)
                else:
                    r = await client.get(config.url, headers=config.headers)

                latency = (time.time() - start) * 1000
                latencies.append(latency)

                if r.status_code < 400:
                    success += 1
                else:
                    errors.append(f"HTTP {r.status_code}")

            except Exception as e:
                errors.append(str(e))
                latencies.append(time.time() - start)

        # Warmup
        print(f"Warming up ({config.warmup_requests} requests)...")
        warmup_tasks = [make_request() for _ in range(config.warmup_requests)]
        await asyncio.gather(*warmup_tasks)
        latencies.clear()
        errors.clear()
        success = 0

        # 测试
        print(f"Running test ({config.test_requests} requests, {config.concurrent} concurrent)...")
        semaphore = asyncio.Semaphore(config.concurrent)

        async def bounded():
            async with semaphore:
                await make_request()

        tasks = [bounded() for _ in range(config.test_requests)]
        await asyncio.gather(*tasks)

    # 计算统计
    latencies.sort()
    p50 = latencies[int(len(latencies) * 0.50)] if latencies else 0
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0
    p99 = latencies[int(len(latencies) * 0.99)] if latencies else 0
    avg = statistics.mean(latencies) if latencies else 0
    mi = min(latencies) if latencies else 0
    ma = max(latencies) if latencies else 0

    return PerfResult(
        name=config.name,
        total=config.test_requests,
        success=success,
        errors=len(errors),
        latencies=latencies,
        p50=p50,
        p95=p95,
        p99=p99,
        avg=avg,
        min=mi,
        max=ma,
    )


def print_result(result: PerfResult, target_p99: float):
    """打印结果"""
    passed = result.passed(target_p99)
    status = "✓ PASS" if passed else "✗ FAIL"

    print(f"\nResults for {result.name}:")
    print(f"  Status:    {status}")
    print(f"  Total:     {result.total}")
    print(f"  Success:   {result.success} ({result.success/result.total*100:.1f}%)")
    print(f"  Errors:    {result.errors}")
    print(f"\nLatency:")
    print(f"  Min:       {result.min:.2f}ms")
    print(f"  Avg:       {result.avg:.2f}ms")
    print(f"  P50:       {result.p50:.2f}ms")
    print(f"  P95:       {result.p95:.2f}ms")
    print(f"  P99:       {result.p99:.2f}ms  (target: <{target_p99}ms)")
    print(f"  Max:       {result.max:.2f}ms")

    if result.errors > 0:
        print(f"\nErrors:")
        error_counts = {}
        for e in result.errors:
            error_counts[e] = error_counts.get(e, 0) + 1
        for e, c in sorted(error_counts.items(), key=lambda x: -x[1])[:5]:
            print(f"  {e}: {c}")


async def main():
    """运行所有性能测试"""
    target_p99 = 100.0  # P99 延迟目标: < 100ms

    print("\n" + "=" * 60)
    print("AI Eval Platform Performance Verification")
    print(f"Target P99 Latency: < {target_p99}ms")
    print("=" * 60)

    # 测试配置
    tests = [
        PerfTestConfig(
            url="http://localhost:8000/v1/evaluate",
            name="Evaluate Endpoint",
            method="POST",
            json_data={
                "model": "gpt-4",
                "input": "What is the capital of France?",
                "expected": "Paris",
            },
            warmup_requests=20,
            test_requests=200,
            concurrent=10,
        ),
        PerfTestConfig(
            url="http://localhost:8000/v1/batch",
            name="Batch Endpoint",
            method="POST",
            json_data={
                "model": "gpt-4",
                "requests": [
                    {"input": "What is 1+1?", "expected": "2"},
                    {"input": "What is 2+2?", "expected": "4"},
                ] * 5,  # 10 requests
            },
            warmup_requests=10,
            test_requests=100,
            concurrent=5,
        ),
        PerfTestConfig(
            url="http://localhost:8000/v1/models",
            name="List Models Endpoint",
            method="GET",
            warmup_requests=20,
            test_requests=200,
            concurrent=10,
        ),
        PerfTestConfig(
            url="http://localhost:8000/health",
            name="Health Check",
            method="GET",
            warmup_requests=10,
            test_requests=100,
            concurrent=20,
        ),
    ]

    results = []
    all_passed = True

    for test in tests:
        try:
            result = await test_endpoint(test)
            results.append(result)
            print_result(result, target_p99)
            if not result.passed(target_p99):
                all_passed = False
        except Exception as e:
            print(f"\nError testing {test.name}: {e}")
            all_passed = False

    # 总结
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed_count = sum(1 for r in results if r.passed(target_p99))
    print(f"\nTests Passed: {passed_count}/{len(results)}")

    if results:
        # 加权平均 P99
        weighted_p99 = sum(r.p99 * r.total for r in results) / sum(r.total for r in results)
        print(f"Weighted Avg P99: {weighted_p99:.2f}ms")

    print(f"\nTarget P99: < {target_p99}ms")

    if all_passed and results:
        print("\n✓ ALL PERFORMANCE TESTS PASSED!")
        print("  P99 latency is below 100ms threshold.")
    else:
        print("\n✗ PERFORMANCE TESTS FAILED")
        print("  Some endpoints exceed the 100ms P99 threshold.")

    print("\n" + "=" * 60)

    return all_passed


if __name__ == "__main__":
    asyncio.run(main())
