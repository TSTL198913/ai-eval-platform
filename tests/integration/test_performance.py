"""
性能优化模块集成测试
覆盖LRU缓存、分段锁、连接池优化、异步批处理
"""

import asyncio
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from src.infra.performance import (
    CacheConfig,
    CacheEntry,
    SegmentLock,
    LRUCache,
    cached,
)


class TestCacheConfig:
    """缓存配置测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = CacheConfig()
        assert config.max_size == 1000
        assert config.ttl_seconds == 300.0
        assert config.eviction_policy == "lru"
        assert config.segment_count == 16

    def test_custom_config(self):
        """测试自定义配置"""
        config = CacheConfig(
            max_size=500,
            ttl_seconds=60.0,
            eviction_policy="lfu",
            segment_count=8,
        )
        assert config.max_size == 500
        assert config.ttl_seconds == 60.0
        assert config.segment_count == 8


class TestCacheEntry:
    """缓存条目测试"""

    def test_cache_entry_basic(self):
        """测试缓存条目基本属性"""
        entry = CacheEntry(value={"data": "test"})
        assert entry.value == {"data": "test"}
        assert entry.hits == 0
        assert entry.is_expired() is False

    def test_cache_entry_expired(self):
        """测试过期缓存条目"""
        entry = CacheEntry(value={"data": "test"}, expires_at=time.time() - 100)
        assert entry.is_expired() is True

    def test_cache_entry_increment_hit(self):
        """测试增加命中计数"""
        entry = CacheEntry(value={"data": "test"})
        entry.increment_hit()
        assert entry.hits == 1
        entry.increment_hit()
        assert entry.hits == 2

    def test_cache_entry_post_init(self):
        """测试post_init设置过期时间"""
        entry = CacheEntry(value={"data": "test"})
        assert entry.expires_at > time.time()


class TestSegmentLock:
    """分段锁集成测试"""

    def test_segment_lock_basic(self):
        """测试分段锁基本功能"""
        segment_lock = SegmentLock(segment_count=16)
        assert len(segment_lock._locks) == 16

    def test_get_lock(self):
        """测试获取锁"""
        segment_lock = SegmentLock(segment_count=16)
        lock1 = segment_lock.get_lock("key1")
        lock2 = segment_lock.get_lock("key2")
        lock3 = segment_lock.get_lock("key1")

        assert lock1 is not None
        assert lock3 is lock1

    def test_get_all_locks(self):
        """测试获取所有锁"""
        segment_lock = SegmentLock(segment_count=4)
        locks = segment_lock.get_all_locks()
        assert len(locks) == 4

    def test_segment_lock_concurrency(self):
        """测试分段锁并发"""
        segment_lock = SegmentLock(segment_count=8)
        errors = []

        def worker(key_prefix):
            try:
                for i in range(100):
                    key = f"{key_prefix}_{i}"
                    with segment_lock.get_lock(key):
                        pass
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=worker, args=("group1",)),
            threading.Thread(target=worker, args=("group2",)),
            threading.Thread(target=worker, args=("group3",)),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


class TestLRUCache:
    """LRU缓存集成测试"""

    def test_cache_get_set(self):
        """测试缓存获取和设置"""
        cache = LRUCache()
        asyncio.run(cache.set("key1", {"data": "value1"}))
        result = asyncio.run(cache.get("key1"))

        assert result == {"data": "value1"}

    def test_cache_expiry(self):
        """测试缓存过期"""
        cache = LRUCache()
        asyncio.run(cache.set("key1", {"data": "value1"}, ttl=0.1))
        result = asyncio.run(cache.get("key1"))
        assert result is not None

        time.sleep(0.2)
        result = asyncio.run(cache.get("key1"))
        assert result is None

    def test_cache_eviction(self):
        """测试缓存淘汰"""
        cache = LRUCache(CacheConfig(max_size=3))

        asyncio.run(cache.set("key1", "value1"))
        asyncio.run(cache.set("key2", "value2"))
        asyncio.run(cache.set("key3", "value3"))

        # 访问key1使其变为最近使用
        asyncio.run(cache.get("key1"))

        # 添加新key，key2应该被淘汰
        asyncio.run(cache.set("key4", "value4"))

        assert asyncio.run(cache.get("key1")) == "value1"
        assert asyncio.run(cache.get("key2")) is None
        assert asyncio.run(cache.get("key3")) == "value3"
        assert asyncio.run(cache.get("key4")) == "value4"

    def test_cache_delete(self):
        """测试缓存删除"""
        cache = LRUCache()
        asyncio.run(cache.set("key1", "value1"))
        result = asyncio.run(cache.delete("key1"))

        assert result is True
        assert asyncio.run(cache.get("key1")) is None

    def test_cache_clear(self):
        """测试清空缓存"""
        cache = LRUCache()
        asyncio.run(cache.set("key1", "value1"))
        asyncio.run(cache.set("key2", "value2"))

        asyncio.run(cache.clear())

        assert cache.size() == 0
        assert asyncio.run(cache.get("key1")) is None

    def test_cache_stats(self):
        """测试缓存统计"""
        cache = LRUCache()

        asyncio.run(cache.set("key1", "value1"))
        asyncio.run(cache.get("key1"))  # hit
        asyncio.run(cache.get("key2"))  # miss
        asyncio.run(cache.get("key1"))  # hit

        stats = cache.get_stats()
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["size"] == 1
        assert stats["hit_rate"] == 2/3

    def test_cache_size(self):
        """测试缓存大小"""
        cache = LRUCache()
        assert cache.size() == 0

        asyncio.run(cache.set("key1", "value1"))
        assert cache.size() == 1

        asyncio.run(cache.set("key2", "value2"))
        assert cache.size() == 2

    def test_cache_overwrite(self):
        """测试缓存覆盖"""
        cache = LRUCache()
        asyncio.run(cache.set("key1", "value1"))
        asyncio.run(cache.set("key1", "value2"))

        result = asyncio.run(cache.get("key1"))
        assert result == "value2"
        assert cache.size() == 1

    def test_cache_concurrent_access(self):
        """测试缓存并发访问"""
        cache = LRUCache()
        errors = []

        def writer():
            try:
                for i in range(100):
                    asyncio.run(cache.set(f"key_{i}", f"value_{i}"))
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for i in range(100):
                    asyncio.run(cache.get(f"key_{i}"))
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


class TestCachedDecorator:
    """缓存装饰器测试"""

    def test_cached_decorator_basic(self):
        """测试缓存装饰器基本功能"""
        cache = LRUCache()

        @cached(cache)
        async def expensive_function(x):
            await asyncio.sleep(0.01)
            return x * 2

        # 第一次调用
        start = time.time()
        result1 = asyncio.run(expensive_function(5))
        elapsed1 = time.time() - start

        # 第二次调用（应该从缓存获取）
        start = time.time()
        result2 = asyncio.run(expensive_function(5))
        elapsed2 = time.time() - start

        assert result1 == 10
        assert result2 == 10
        assert elapsed2 < elapsed1 * 0.5

    def test_cached_decorator_with_key_generator(self):
        """测试带key生成器的缓存装饰器"""
        cache = LRUCache()

        def key_gen(a, b):
            return f"{a}_{b}"

        @cached(cache, key_generator=key_gen)
        async def add(a, b):
            return a + b

        asyncio.run(add(1, 2))
        result = asyncio.run(add(1, 2))
        assert result == 3

    def test_cached_decorator_with_ttl(self):
        """测试带TTL的缓存装饰器"""
        cache = LRUCache()

        @cached(cache, ttl=0.05)
        async def get_time():
            return time.time()

        result1 = asyncio.run(get_time())
        asyncio.run(asyncio.sleep(0.06))
        result2 = asyncio.run(get_time())

        assert result2 > result1 + 0.04


class TestLRUCacheEdgeCases:
    """LRU缓存边界情况测试"""

    def test_empty_key(self):
        """测试空key"""
        cache = LRUCache()
        asyncio.run(cache.set("", "empty"))
        result = asyncio.run(cache.get(""))
        assert result == "empty"

    def test_none_value(self):
        """测试None值"""
        cache = LRUCache()
        asyncio.run(cache.set("key1", None))
        result = asyncio.run(cache.get("key1"))
        assert result is None

    def test_special_characters_key(self):
        """测试特殊字符key"""
        cache = LRUCache()
        asyncio.run(cache.set("key:with:special/characters", "value"))
        result = asyncio.run(cache.get("key:with:special/characters"))
        assert result == "value"

    def test_large_value(self):
        """测试大值"""
        cache = LRUCache()
        large_value = {"data": "x" * 10000}
        asyncio.run(cache.set("large_key", large_value))
        result = asyncio.run(cache.get("large_key"))
        assert result["data"] == "x" * 10000

    def test_zero_max_size(self):
        """测试max_size为0"""
        cache = LRUCache(CacheConfig(max_size=0))
        asyncio.run(cache.set("key1", "value1"))
        result = asyncio.run(cache.get("key1"))
        assert result is None


class TestCacheIntegration:
    """缓存集成测试"""

    def test_cache_with_segment_lock(self):
        """测试缓存与分段锁组合"""
        cache = LRUCache(CacheConfig(segment_count=8))

        asyncio.run(cache.set("key1", "value1"))
        asyncio.run(cache.set("key2", "value2"))

        assert asyncio.run(cache.get("key1")) == "value1"
        assert asyncio.run(cache.get("key2")) == "value2"

    def test_full_cache_flow(self):
        """测试完整缓存流程"""
        cache = LRUCache()

        # 设置缓存
        asyncio.run(cache.set("user_1", {"name": "Alice", "age": 30}))

        # 获取缓存
        user = asyncio.run(cache.get("user_1"))
        assert user["name"] == "Alice"

        # 更新缓存
        asyncio.run(cache.set("user_1", {"name": "Alice", "age": 31}))
        user = asyncio.run(cache.get("user_1"))
        assert user["age"] == 31

        # 获取统计
        stats = cache.get_stats()
        assert stats["hits"] >= 1

        # 删除缓存
        asyncio.run(cache.delete("user_1"))
        assert asyncio.run(cache.get("user_1")) is None