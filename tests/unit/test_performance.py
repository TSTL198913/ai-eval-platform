"""测试 src/infra/performance.py - 性能优化模块"""

import asyncio
import time
from unittest.mock import AsyncMock, Mock

import pytest

from src.infra.performance import (
    BatchProcessor,
    CacheConfig,
    CacheEntry,
    ConnectionPoolMonitor,
    LRUCache,
    PerformanceOptimizer,
    cached,
)


class TestLRUCache:
    """测试 LRU 缓存"""

    @pytest.fixture
    def cache(self):
        return LRUCache(CacheConfig(max_size=3, ttl_seconds=1.0))

    @pytest.mark.asyncio
    async def test_set_and_get(self, cache):
        """测试设置和获取"""
        await cache.set("key1", "value1")
        result = await cache.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_cache_miss(self, cache):
        """测试缓存未命中"""
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_lru_eviction(self, cache):
        """测试 LRU 淘汰"""
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")
        await cache.set("key4", "value4")  # 触发淘汰

        # key1 应该被淘汰
        result = await cache.get("key1")
        assert result is None

        # key2 应该存在
        result = await cache.get("key2")
        assert result == "value2"

    @pytest.mark.asyncio
    async def test_expiration(self, cache):
        """测试过期"""
        await cache.set("key1", "value1", ttl=0.01)
        await asyncio.sleep(0.02)

        result = await cache.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self, cache):
        """测试删除"""
        await cache.set("key1", "value1")
        deleted = await cache.delete("key1")
        assert deleted is True

        result = await cache.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_clear(self, cache):
        """测试清空"""
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.clear()

        assert len(cache._cache) == 0

    @pytest.mark.asyncio
    async def test_stats(self, cache):
        """测试统计"""
        await cache.set("key1", "value1")
        await cache.get("key1")  # hit
        await cache.get("key2")  # miss

        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5


class TestCacheEntry:
    """测试缓存条目"""

    def test_creation(self):
        """测试创建"""
        entry = CacheEntry(value="test", key="key1")
        assert entry.value == "test"
        assert entry.key == "key1"
        assert entry.hits == 0

    def test_is_expired(self):
        """测试过期检查"""
        entry = CacheEntry(value="test", expires_at=time.time() - 1)
        assert entry.is_expired() is True

        entry2 = CacheEntry(value="test", expires_at=time.time() + 100)
        assert entry2.is_expired() is False

    def test_increment_hit(self):
        """测试命中计数"""
        entry = CacheEntry(value="test")
        entry.increment_hit()
        entry.increment_hit()
        assert entry.hits == 2


class TestBatchProcessor:
    """测试批处理器"""

    @pytest.fixture
    async def processor(self):
        processor = BatchProcessor(batch_size=3, batch_timeout=0.01)
        await processor.start()  # 异步启动批处理器
        yield processor
        await processor.stop()  # 异步清理

    @pytest.mark.asyncio
    async def test_add_item(self, processor):
        """测试添加项"""
        result = await processor.add("item1")
        assert result == "item1"  # 默认返回原项

    @pytest.mark.asyncio
    async def test_batch_execution(self, processor):
        """测试批量执行"""
        processor._execute_batch = AsyncMock(return_value=["result1", "result2"])

        # 并发添加两个项，确保在同一批处理中
        result1, result2 = await asyncio.gather(processor.add("item1"), processor.add("item2"))

        # 验证结果
        assert result1 == "result1"
        assert result2 == "result2"


class TestConnectionPoolMonitor:
    """测试连接池监控"""

    @pytest.fixture
    def monitor(self):
        return ConnectionPoolMonitor()

    def test_register_pool(self, monitor):
        """测试注册连接池"""
        mock_pool = Mock()
        monitor.register_pool("redis", mock_pool)

        stats = monitor.get_pool_stats("redis")
        assert stats is not None

    def test_update_metrics(self, monitor):
        """测试更新指标"""
        monitor._metrics["test"] = {}
        monitor.update_metrics("test", {"active_connections": 10})

        assert monitor._metrics["test"]["active_connections"] == 10

    def test_get_health_status(self, monitor):
        """测试健康状态"""
        monitor._metrics["redis"] = {
            "total_connections": 10,
            "active_connections": 10,  # 100%，超过阈值
            "idle_connections": 0,
        }

        health = monitor.get_health_status()
        assert health["healthy"] is False
        assert len(health["issues"]) > 0


class TestPerformanceOptimizer:
    """测试性能优化器"""

    @pytest.fixture
    def optimizer(self):
        return PerformanceOptimizer()

    @pytest.mark.asyncio
    async def test_initialize(self, optimizer):
        """测试初始化"""
        await optimizer.initialize()
        assert optimizer._initialized is True

    @pytest.mark.asyncio
    async def test_shutdown(self, optimizer):
        """测试关闭"""
        await optimizer.initialize()
        await optimizer.shutdown()
        assert optimizer._initialized is False

    def test_get_components(self, optimizer):
        """测试获取组件"""
        assert optimizer.get_cache() is not None
        assert optimizer.get_batch_processor() is not None
        assert optimizer.get_pool_monitor() is not None

    def test_get_all_stats(self, optimizer):
        """测试获取所有统计"""
        stats = optimizer.get_all_stats()
        assert "cache" in stats
        assert "pools" in stats


class TestCachedDecorator:
    """测试缓存装饰器"""

    @pytest.mark.asyncio
    async def test_cached_decorator(self):
        """测试缓存装饰器"""
        cache = LRUCache()

        call_count = 0

        @cached(cache, key_generator=lambda x: f"compute:{x}")
        async def expensive_compute(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        # 第一次调用
        result1 = await expensive_compute(5)
        assert result1 == 10
        assert call_count == 1

        # 第二次调用（应该命中缓存）
        result2 = await expensive_compute(5)
        assert result2 == 10
        assert call_count == 1  # 未增加

        # 不同参数
        result3 = await expensive_compute(10)
        assert result3 == 20
        assert call_count == 2
