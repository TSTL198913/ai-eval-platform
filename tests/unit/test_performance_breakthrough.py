"""测试 src/infra/performance_breakthrough.py - 性能突破模块"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.infra.performance_breakthrough import (
    CacheOptimizer,
    ConnectionOptimizer,
    LatencyTracker,
    PerformanceBreakthrough,
    PerformanceTarget,
    RequestOptimizer,
    get_performance_optimizer,
    track_performance,
)


class TestPerformanceTarget:
    """测试性能目标"""

    def test_default_values(self):
        target = PerformanceTarget()
        assert target.p50_ms == 50.0
        assert target.p95_ms == 80.0
        assert target.p99_ms == 100.0
        assert target.max_ms == 200.0
        assert target.throughput_per_sec == 1000

    def test_custom_values(self):
        target = PerformanceTarget(p50_ms=30.0, p99_ms=80.0, throughput_per_sec=2000)
        assert target.p50_ms == 30.0
        assert target.p99_ms == 80.0
        assert target.throughput_per_sec == 2000


class TestLatencyTracker:
    """测试延迟追踪器"""

    @pytest.fixture
    def tracker(self):
        return LatencyTracker(window_size=100)

    @pytest.mark.asyncio
    async def test_record_latency(self, tracker):
        await tracker.record(50.0)
        await tracker.record(100.0)
        assert len(tracker._latencies) == 2

    @pytest.mark.asyncio
    async def test_window_size_limit(self, tracker):
        for i in range(110):
            await tracker.record(float(i))
        assert len(tracker._latencies) == 100
        assert tracker._latencies[0] == 10.0  # 最早的被移除了

    def test_get_percentiles_empty(self, tracker):
        percentiles = tracker.get_percentiles()
        assert percentiles["p50"] == 0
        assert percentiles["p99"] == 0

    @pytest.mark.asyncio
    async def test_get_percentiles(self, tracker):
        for i in range(1, 101):
            await tracker.record(float(i))

        percentiles = tracker.get_percentiles()
        # int(n * 0.50) = 50, index 50 is the 51st element = 51.0
        assert percentiles["p50"] == 51.0
        assert percentiles["p95"] == 96.0  # index 95 = 96th element
        assert percentiles["p99"] == 100.0  # index 99 = 100th element
        assert percentiles["max"] == 100.0
        assert percentiles["avg"] == 50.5

    def test_check_target_meet(self):
        tracker = LatencyTracker()
        tracker._latencies = [10.0, 20.0, 30.0, 40.0, 50.0]

        target = PerformanceTarget(p50_ms=100.0, p95_ms=100.0, p99_ms=100.0, max_ms=100.0)
        result = tracker.check_target(target)
        assert all(result.values())

    def test_check_target_exceed(self):
        tracker = LatencyTracker()
        tracker._latencies = [100.0, 200.0, 300.0, 400.0, 500.0]

        target = PerformanceTarget(p50_ms=50.0, p95_ms=100.0, p99_ms=150.0, max_ms=200.0)
        result = tracker.check_target(target)
        assert not any(result.values())

    def test_check_target_partial(self):
        tracker = LatencyTracker()
        # 100 elements, p95 = index 95 = 96th element
        tracker._latencies = [float(i) for i in range(1, 101)]

        target = PerformanceTarget(p50_ms=60.0, p95_ms=100.0, p99_ms=150.0, max_ms=50.0)
        result = tracker.check_target(target)
        assert result["p50_ok"] is True  # p50=51 <= 60
        assert result["p95_ok"] is True  # p95=96 <= 100
        assert result["p99_ok"] is True  # p99=100 <= 150
        assert result["max_ok"] is False  # max=100 > 50


class TestRequestOptimizer:
    """测试请求优化器"""

    @pytest.fixture
    def optimizer(self):
        return RequestOptimizer()

    @pytest.mark.asyncio
    async def test_optimize_request_new(self, optimizer):
        handler = AsyncMock(return_value="result")
        result = await optimizer.optimize_request("req-1", handler)
        assert result == "result"
        handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_optimize_request_precomputed(self, optimizer):
        optimizer.precompute("req-1", "cached")
        handler = AsyncMock(return_value="new_result")
        result = await optimizer.optimize_request("req-1", handler)
        assert result == "cached"
        handler.assert_not_called()

    def test_precompute(self, optimizer):
        optimizer.precompute("req-1", {"data": 123})
        assert optimizer._precomputed_results["req-1"] == {"data": 123}

    @pytest.mark.asyncio
    async def test_batch_process(self, optimizer):
        async def handler1():
            return "result1"

        async def handler2():
            return "result2"

        requests = [("req-1", handler1), ("req-2", handler2)]
        results = await optimizer.batch_process(requests)
        assert results == ["result1", "result2"]


class TestConnectionOptimizer:
    """测试连接优化器"""

    def test_optimize_pool_config(self):
        optimizer = ConnectionOptimizer()
        config = optimizer.optimize_pool_config()

        assert "pool_size" in config
        assert "keep_alive_timeout" in config
        assert "connection_timeout" in config
        assert "max_overflow" in config
        assert "pool_recycle" in config
        assert config["pool_size"] == 50


class TestCacheOptimizer:
    """测试缓存优化器"""

    @pytest.fixture
    def cache(self):
        return CacheOptimizer()

    @pytest.mark.asyncio
    async def test_get_from_l1(self, cache):
        cache._l1_cache["key1"] = "value1"
        result = await cache.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_get_not_found(self, cache):
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_and_get(self, cache):
        await cache.set("key1", "value1")
        result = await cache.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_set_l1_size_limit(self, cache):
        cache._l1_max_size = 2
        await cache.set("k1", "v1")
        await cache.set("k2", "v2")
        await cache.set("k3", "v3")
        # L1 应只有 2 个
        assert len(cache._l1_cache) <= 2

    def test_clear_l1(self, cache):
        cache._l1_cache["key"] = "value"
        cache.clear_l1()
        assert cache._l1_cache == {}


class TestPerformanceBreakthrough:
    """测试性能突破管理器"""

    @pytest.fixture
    def pb(self):
        return PerformanceBreakthrough()

    @pytest.mark.asyncio
    async def test_process_request_with_cache(self, pb):
        # 预热缓存
        await pb._cache_optimizer.set("req-1", "cached_value")

        handler = AsyncMock(return_value="new_value")
        result, latency = await pb.process_request("req-1", handler)

        assert result == "cached_value"
        handler.assert_not_called()
        assert latency >= 0

    @pytest.mark.asyncio
    async def test_process_request_without_cache(self, pb):
        handler = AsyncMock(return_value="computed_value")
        result, latency = await pb.process_request("req-2", handler)

        assert result == "computed_value"
        handler.assert_called_once()
        assert latency >= 0
        # 结果应被缓存
        cached = await pb._cache_optimizer.get("req-2")
        assert cached == "computed_value"

    def test_get_performance_report(self, pb):
        report = pb.get_performance_report()

        assert "target" in report
        assert "actual" in report
        assert "status" in report
        assert "overall_ok" in report
        assert isinstance(report["overall_ok"], bool)

    def test_get_optimization_stats(self, pb):
        stats = pb.get_optimization_stats()

        assert "cache" in stats
        assert "connections" in stats
        assert "requests" in stats
        assert "l1_size" in stats["cache"]
        assert "precomputed" in stats["requests"]


class TestTrackPerformance:
    """测试性能追踪装饰器"""

    @pytest.mark.asyncio
    async def test_decorator_records_latency(self):
        tracker = LatencyTracker()

        @track_performance(tracker)
        async def slow_func():
            await asyncio.sleep(0.01)
            return "done"

        result = await slow_func()
        assert result == "done"
        assert len(tracker._latencies) == 1
        assert tracker._latencies[0] >= 10.0  # 至少 10ms


class TestGlobalOptimizer:
    """测试全局优化器"""

    def test_get_performance_optimizer_singleton(self):
        opt1 = get_performance_optimizer()
        opt2 = get_performance_optimizer()
        assert opt1 is opt2
        assert isinstance(opt1, PerformanceBreakthrough)
