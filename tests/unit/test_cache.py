import asyncio
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from src.infra.cache import EvaluationCache, cached
from src.infra.performance import CacheConfig, LRUCache, SegmentLock


class TestEvaluationCache:
    """评估缓存测试"""

    def test_get_set(self):
        """测试缓存存取"""
        cache = EvaluationCache(ttl_seconds=60)
        cache.set("key1", "value1")

        assert cache.get("key1") == "value1"

    def test_get_missing_key(self):
        """测试获取不存在的key"""
        cache = EvaluationCache(ttl_seconds=60)

        assert cache.get("missing") is None

    def test_ttl_expiration(self):
        """测试TTL过期"""
        cache = EvaluationCache(ttl_seconds=0)
        cache.set("key1", "value1")

        assert cache.get("key1") is None

    def test_invalidate(self):
        """测试删除缓存"""
        cache = EvaluationCache(ttl_seconds=60)
        cache.set("key1", "value1")
        cache.invalidate("key1")

        assert cache.get("key1") is None

    def test_invalidate_missing(self):
        """测试删除不存在的key不报错"""
        cache = EvaluationCache(ttl_seconds=60)
        cache.invalidate("missing")

        assert cache.get("missing") is None

    def test_clear(self):
        """测试清空缓存"""
        cache = EvaluationCache(ttl_seconds=60)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()

        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_max_size_limit(self):
        """测试容量限制"""
        cache = EvaluationCache(ttl_seconds=60, max_size=3)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        cache.set("key4", "value4")  # 应该触发淘汰

        # 容量应该不超过max_size
        assert cache.size() == 3

    def test_lru_eviction(self):
        """测试LRU淘汰机制"""
        cache = EvaluationCache(ttl_seconds=60, max_size=3)

        # 添加3个元素
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        # 访问key1，使其变为最近使用
        cache.get("key1")

        # 添加新元素，应该淘汰key2（最久未使用）
        cache.set("key4", "value4")

        # key1应该存在（最近被访问）
        assert cache.get("key1") == "value1"
        # key2应该被淘汰
        assert cache.get("key2") is None
        # key3和key4应该存在
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"

    def test_lru_eviction_order(self):
        """测试LRU淘汰顺序"""
        cache = EvaluationCache(ttl_seconds=60, max_size=2)

        cache.set("a", "1")
        cache.set("b", "2")
        # 缓存: [a, b]

        cache.get("a")  # a变为最近使用
        # 缓存顺序: [b, a]

        cache.set("c", "3")  # 淘汰b
        # 缓存: [a, c]

        assert cache.get("a") == "1"
        assert cache.get("b") is None  # 被淘汰
        assert cache.get("c") == "3"

    def test_update_existing_key(self):
        """测试更新已存在的键"""
        cache = EvaluationCache(ttl_seconds=60, max_size=2)

        cache.set("key1", "value1")
        cache.set("key1", "value2")  # 更新

        assert cache.get("key1") == "value2"
        assert cache.size() == 1

    def test_get_stats(self):
        """测试统计信息"""
        cache = EvaluationCache(ttl_seconds=60, max_size=100)

        cache.set("key1", "value1")
        cache.get("key1")  # hit
        cache.get("key2")  # miss

        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1
        assert stats["max_size"] == 100
        assert stats["hit_rate"] == 0.5

    def test_stats_evictions(self):
        """测试淘汰统计"""
        cache = EvaluationCache(ttl_seconds=60, max_size=2)

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")  # 触发淘汰

        stats = cache.get_stats()
        assert stats["evictions"] == 1

    def test_concurrent_access(self):
        """测试并发访问"""
        cache = EvaluationCache(ttl_seconds=60, max_size=1000)
        errors = []
        iterations = 100

        def writer(start_key: int):
            try:
                for i in range(iterations):
                    cache.set(f"key_{start_key}_{i}", f"value_{i}")
            except Exception as e:
                errors.append(e)

        def reader(start_key: int):
            try:
                for i in range(iterations):
                    cache.get(f"key_{start_key}_{i}")
            except Exception as e:
                errors.append(e)

        # 创建多个读写线程
        threads = []
        for i in range(5):
            threads.append(threading.Thread(target=writer, args=(i,)))
            threads.append(threading.Thread(target=reader, args=(i,)))

        # 启动所有线程
        for t in threads:
            t.start()

        # 等待所有线程完成
        for t in threads:
            t.join()

        # 不应该有错误
        assert len(errors) == 0

    def test_concurrent_eviction(self):
        """测试并发淘汰"""
        cache = EvaluationCache(ttl_seconds=60, max_size=10)
        errors = []

        def writer(thread_id: int):
            try:
                for i in range(100):
                    cache.set(f"t{thread_id}_key{i}", f"value{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert cache.size() <= 10


class TestCachedDecorator:
    """缓存装饰器测试"""

    def test_cached_result(self):
        """测试缓存命中"""
        call_count = 0

        @cached(key_prefix="test")
        def my_func(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        result1 = my_func(5)
        result2 = my_func(5)

        assert result1 == 10
        assert result2 == 10
        assert call_count == 1

    def test_cached_different_args(self):
        """测试不同参数分别缓存"""
        call_count = 0

        @cached(key_prefix="test2")
        def my_func(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        result1 = my_func(5)
        result2 = my_func(10)

        assert result1 == 10
        assert result2 == 20
        assert call_count == 2


class TestBatchInsert:
    """批量插入测试"""

    def test_batch_insert_empty(self):
        """测试空列表插入"""
        from src.infra.cache import batch_insert

        result = batch_insert([])
        assert result == 0

    @patch("src.infra.cache.get_db_session")
    def test_batch_insert_records(self, mock_get_session):
        """测试批量插入记录"""
        from src.infra.cache import batch_insert

        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        results = [
            {"case_id": "c1", "status": "passed"},
            {"case_id": "c2", "status": "failed"},
        ]

        count = batch_insert(results)
        assert count == 2
        mock_session.add_all.assert_called_once()
        mock_session.commit.assert_called_once()


class TestSegmentLock:
    """分段锁测试"""

    def test_segment_lock_creation(self):
        """测试分段锁创建"""
        lock = SegmentLock(segment_count=16)
        assert len(lock._locks) == 16

    def test_get_lock_consistency(self):
        """测试相同键获取相同锁"""
        lock = SegmentLock(segment_count=16)
        lock1 = lock.get_lock("test_key")
        lock2 = lock.get_lock("test_key")
        assert lock1 is lock2

    def test_get_lock_different_keys(self):
        """测试不同键可能获取不同锁"""
        lock = SegmentLock(segment_count=16)
        lock1 = lock.get_lock("key1")
        lock2 = lock.get_lock("key2")
        # 不同键可能映射到相同或不同的锁
        assert isinstance(lock1, type(lock2))

    def test_get_all_locks(self):
        """测试获取所有锁"""
        lock = SegmentLock(segment_count=8)
        all_locks = lock.get_all_locks()
        assert len(all_locks) == 8


class TestLRUCache:
    """LRU缓存测试"""

    @pytest.mark.asyncio
    async def test_async_get_set(self):
        """测试异步缓存存取"""
        config = CacheConfig(max_size=100, ttl_seconds=60)
        cache = LRUCache(config)

        await cache.set("key1", "value1")
        result = await cache.get("key1")

        assert result == "value1"

    @pytest.mark.asyncio
    async def test_async_missing_key(self):
        """测试异步获取不存在的键"""
        cache = LRUCache()
        result = await cache.get("missing")
        assert result is None

    @pytest.mark.asyncio
    async def test_async_ttl_expiration(self):
        """测试异步TTL过期"""
        config = CacheConfig(max_size=100, ttl_seconds=0.01)
        cache = LRUCache(config)

        await cache.set("key1", "value1")
        await asyncio.sleep(0.02)  # 等待过期
        result = await cache.get("key1")

        assert result is None

    @pytest.mark.asyncio
    async def test_async_max_size_eviction(self):
        """测试异步容量淘汰"""
        config = CacheConfig(max_size=3, ttl_seconds=60)
        cache = LRUCache(config)

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")
        await cache.set("key4", "value4")  # 应该淘汰key1

        assert await cache.get("key1") is None
        assert await cache.get("key4") == "value4"
        assert cache.size() == 3

    @pytest.mark.asyncio
    async def test_async_lru_eviction_order(self):
        """测试异步LRU淘汰顺序"""
        config = CacheConfig(max_size=2, ttl_seconds=60)
        cache = LRUCache(config)

        await cache.set("a", "1")
        await cache.set("b", "2")
        await cache.get("a")  # a变为最近使用
        await cache.set("c", "3")  # 淘汰b

        assert await cache.get("a") == "1"
        assert await cache.get("b") is None
        assert await cache.get("c") == "3"

    @pytest.mark.asyncio
    async def test_async_delete(self):
        """测试异步删除"""
        cache = LRUCache()

        await cache.set("key1", "value1")
        result = await cache.delete("key1")
        assert result is True

        result = await cache.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_async_delete_missing(self):
        """测试异步删除不存在的键"""
        cache = LRUCache()
        result = await cache.delete("missing")
        assert result is False

    @pytest.mark.asyncio
    async def test_async_clear(self):
        """测试异步清空缓存"""
        cache = LRUCache()

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.clear()

        assert cache.size() == 0

    @pytest.mark.asyncio
    async def test_async_stats(self):
        """测试异步统计信息"""
        config = CacheConfig(max_size=100, ttl_seconds=60)
        cache = LRUCache(config)

        await cache.set("key1", "value1")
        await cache.get("key1")  # hit
        await cache.get("key2")  # miss

        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1

    @pytest.mark.asyncio
    async def test_async_concurrent_access(self):
        """测试异步并发访问"""
        config = CacheConfig(max_size=1000, ttl_seconds=60)
        cache = LRUCache(config)

        async def writer(start_key: int):
            for i in range(50):
                await cache.set(f"key_{start_key}_{i}", f"value_{i}")

        async def reader(start_key: int):
            for i in range(50):
                await cache.get(f"key_{start_key}_{i}")

        # 并发执行
        tasks = []
        for i in range(5):
            tasks.append(writer(i))
            tasks.append(reader(i))

        await asyncio.gather(*tasks)

        # 验证缓存大小不超过限制
        assert cache.size() <= 1000

    @pytest.mark.asyncio
    async def test_custom_ttl(self):
        """测试自定义TTL"""
        config = CacheConfig(max_size=100, ttl_seconds=60)
        cache = LRUCache(config)

        # 使用自定义短TTL
        await cache.set("key1", "value1", ttl=0.01)
        await asyncio.sleep(0.02)
        result = await cache.get("key1")

        assert result is None

    @pytest.mark.asyncio
    async def test_update_existing_key(self):
        """测试更新已存在的键"""
        cache = LRUCache()

        await cache.set("key1", "value1")
        await cache.set("key1", "value2")

        result = await cache.get("key1")
        assert result == "value2"
        assert cache.size() == 1


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
            max_size=5000,
            ttl_seconds=600.0,
            eviction_policy="lfu",
            segment_count=32,
        )
        assert config.max_size == 5000
        assert config.ttl_seconds == 600.0
        assert config.eviction_policy == "lfu"
        assert config.segment_count == 32


class TestCacheEntry:
    """缓存条目测试"""

    def test_entry_creation(self):
        """测试条目创建"""
        from src.infra.performance import CacheEntry

        entry = CacheEntry(value="test_value")
        assert entry.value == "test_value"
        assert entry.hits == 0
        assert entry.created_at > 0

    def test_entry_expiration(self):
        """测试条目过期"""
        from src.infra.performance import CacheEntry

        entry = CacheEntry(value="test_value", expires_at=time.time() - 1)
        assert entry.is_expired() is True

        entry2 = CacheEntry(value="test_value", expires_at=time.time() + 100)
        assert entry2.is_expired() is False

    def test_entry_increment_hit(self):
        """测试命中计数"""
        from src.infra.performance import CacheEntry

        entry = CacheEntry(value="test_value")
        assert entry.hits == 0
        entry.increment_hit()
        assert entry.hits == 1


class TestCachedDecoratorAsync:
    """异步缓存装饰器测试"""

    @pytest.mark.asyncio
    async def test_cached_decorator_hit(self):
        """测试异步缓存装饰器命中"""
        from src.infra.performance import cached

        config = CacheConfig(max_size=100, ttl_seconds=60)
        cache = LRUCache(config)
        call_count = 0

        @cached(cache)
        async def my_async_func(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        # 第一次调用，缓存miss
        result1 = await my_async_func(5)
        assert result1 == 10
        assert call_count == 1

        # 第二次调用，缓存hit
        result2 = await my_async_func(5)
        assert result2 == 10
        assert call_count == 1  # 没有增加

    @pytest.mark.asyncio
    async def test_cached_decorator_different_args(self):
        """测试异步缓存装饰器不同参数"""
        from src.infra.performance import cached

        cache = LRUCache()
        call_count = 0

        @cached(cache)
        async def my_async_func(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        result1 = await my_async_func(5)
        result2 = await my_async_func(10)

        assert result1 == 10
        assert result2 == 20
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_cached_decorator_custom_key_generator(self):
        """测试异步缓存装饰器自定义键生成器"""
        from src.infra.performance import cached

        cache = LRUCache()
        call_count = 0

        def key_gen(x, y):
            return f"custom:{x}:{y}"

        @cached(cache, key_generator=key_gen)
        async def my_async_func(x, y):
            nonlocal call_count
            call_count += 1
            return x + y

        result1 = await my_async_func(1, 2)
        result2 = await my_async_func(1, 2)

        assert result1 == 3
        assert result2 == 3
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_cached_decorator_custom_ttl(self):
        """测试异步缓存装饰器自定义TTL"""
        from src.infra.performance import cached

        cache = LRUCache()
        call_count = 0

        @cached(cache, ttl=0.01)
        async def my_async_func(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        result1 = await my_async_func(5)
        assert result1 == 10
        assert call_count == 1

        # 等待过期
        await asyncio.sleep(0.02)

        # 过期后重新调用
        result2 = await my_async_func(5)
        assert result2 == 10
        assert call_count == 2


class TestLRUCacheEdgeCases:
    """LRU缓存边界情况测试"""

    @pytest.mark.asyncio
    async def test_evict_empty_cache(self):
        """测试空缓存淘汰"""
        cache = LRUCache(CacheConfig(max_size=1))
        # 直接调用_evict（空缓存）
        cache._evict()
        assert cache.size() == 0

    @pytest.mark.asyncio
    async def test_multiple_evictions(self):
        """测试多次淘汰"""
        cache = LRUCache(CacheConfig(max_size=2, ttl_seconds=60))

        # 添加多个元素触发多次淘汰
        for i in range(10):
            await cache.set(f"key{i}", f"value{i}")

        stats = cache.get_stats()
        assert stats["evictions"] >= 8
        assert cache.size() == 2

    @pytest.mark.asyncio
    async def test_hit_rate_zero(self):
        """测试命中率为零"""
        cache = LRUCache()

        # 只有miss，没有hit
        await cache.get("key1")
        await cache.get("key2")

        stats = cache.get_stats()
        assert stats["hit_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_hit_rate_one(self):
        """测试命中率为一"""
        cache = LRUCache()

        await cache.set("key1", "value1")
        await cache.get("key1")  # hit

        stats = cache.get_stats()
        assert stats["hit_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_size_method(self):
        """测试size方法"""
        cache = LRUCache()

        assert cache.size() == 0
        await cache.set("key1", "value1")
        assert cache.size() == 1
        await cache.set("key2", "value2")
        assert cache.size() == 2
        await cache.delete("key1")
        assert cache.size() == 1


class TestEvaluationCacheEdgeCases:
    """EvaluationCache边界情况测试"""

    def test_float_ttl(self):
        """测试浮点数TTL"""
        cache = EvaluationCache(ttl_seconds=0.5)
        cache.set("key1", "value1")

        # 立即获取应该存在
        assert cache.get("key1") == "value1"

        # 等待过期
        time.sleep(0.6)
        assert cache.get("key1") is None

    def test_size_method(self):
        """测试size方法"""
        cache = EvaluationCache(ttl_seconds=60)

        assert cache.size() == 0
        cache.set("key1", "value1")
        assert cache.size() == 1

    def test_clear_resets_stats(self):
        """测试清空缓存重置统计"""
        cache = EvaluationCache(ttl_seconds=60)

        cache.set("key1", "value1")
        cache.get("key1")  # hit
        cache.get("key2")  # miss

        stats_before = cache.get_stats()
        assert stats_before["hits"] == 1
        assert stats_before["misses"] == 1

        cache.clear()

        stats_after = cache.get_stats()
        assert stats_after["hits"] == 0
        assert stats_after["misses"] == 0

    def test_max_size_zero(self):
        """测试max_size为0的情况"""
        cache = EvaluationCache(ttl_seconds=60, max_size=0)
        # max_size为0时，添加元素应该立即被淘汰
        cache.set("key1", "value1")
        # 由于max_size=0，容量检查会触发淘汰
        assert cache.size() == 0

    def test_large_max_size(self):
        """测试大容量缓存"""
        cache = EvaluationCache(ttl_seconds=60, max_size=10000)

        # 添加大量元素
        for i in range(1000):
            cache.set(f"key{i}", f"value{i}")

        assert cache.size() == 1000

        # 验证所有元素都可以获取
        for i in range(1000):
            assert cache.get(f"key{i}") == f"value{i}"


class TestSegmentLockEdgeCases:
    """分段锁边界情况测试"""

    def test_segment_count_one(self):
        """测试单段锁"""
        lock = SegmentLock(segment_count=1)
        lock1 = lock.get_lock("key1")
        lock2 = lock.get_lock("key2")
        assert lock1 is lock2  # 所有键都映射到同一个锁

    def test_segment_count_large(self):
        """测试大段数"""
        lock = SegmentLock(segment_count=100)
        assert len(lock.get_all_locks()) == 100

    def test_lock_acquire_release(self):
        """测试锁获取和释放"""
        lock = SegmentLock(segment_count=4)
        test_lock = lock.get_lock("test_key")

        # 获取锁
        acquired = test_lock.acquire(blocking=False)
        assert acquired is True

        # 释放锁
        test_lock.release()

        # 再次获取应该成功
        acquired2 = test_lock.acquire(blocking=False)
        assert acquired2 is True
        test_lock.release()