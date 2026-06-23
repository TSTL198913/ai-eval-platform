"""
缓存层集成测试
测试目标：验证 EvaluationCache 与 Redis 的完整集成流程
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from src.infra.cache import EvaluationCache, cached, get_redis, get_redis_client


@pytest.fixture
def cache():
    """缓存实例"""
    return EvaluationCache(ttl_seconds=60, max_size=100)


@pytest.fixture
def short_ttl_cache():
    """短TTL缓存实例"""
    return EvaluationCache(ttl_seconds=0.1, max_size=100)


class TestCacheBasicOperations:
    """基础操作测试"""

    def test_get_returns_none_for_missing_key(self, cache):
        """获取不存在的键应返回None"""
        result = cache.get("nonexistent")
        assert result is None

    def test_set_and_get_stores_value(self, cache):
        """设置和获取应存储值"""
        cache.set("key1", "value1")
        result = cache.get("key1")
        assert result == "value1"

    def test_get_updates_access_order(self, cache):
        """获取应更新访问顺序"""
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        cache.get("key1")

        keys = list(cache._cache.keys())
        assert keys[-1] == "key1"

    def test_invalidate_removes_key(self, cache):
        """删除指定键应移除缓存"""
        cache.set("key1", "value1")
        cache.invalidate("key1")
        result = cache.get("key1")
        assert result is None

    def test_clear_removes_all_keys(self, cache):
        """清空应移除所有键"""
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.size() == 0
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_size_returns_correct_count(self, cache):
        """size方法应返回正确计数"""
        assert cache.size() == 0
        cache.set("key1", "value1")
        assert cache.size() == 1
        cache.set("key2", "value2")
        assert cache.size() == 2


class TestCacheTTLMechanism:
    """TTL过期机制测试"""

    def test_expired_key_returns_none(self, short_ttl_cache):
        """过期的键应返回None"""
        short_ttl_cache.set("key1", "value1")
        time.sleep(0.2)
        result = short_ttl_cache.get("key1")
        assert result is None

    def test_non_expired_key_returns_value(self, short_ttl_cache):
        """未过期的键应返回值"""
        short_ttl_cache.set("key1", "value1")
        time.sleep(0.05)
        result = short_ttl_cache.get("key1")
        assert result == "value1"

    def test_custom_ttl_override(self, cache):
        """自定义TTL应覆盖默认TTL"""
        cache._ttl = 0.1
        cache.set("key1", "value1")
        time.sleep(0.2)
        result = cache.get("key1")
        assert result is None


class TestCacheLRUEviction:
    """LRU淘汰策略测试"""

    def test_lru_eviction_when_full(self):
        """缓存满时应淘汰最久未使用的"""
        cache = EvaluationCache(ttl_seconds=60, max_size=3)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        cache.get("key1")

        cache.set("key4", "value4")

        assert cache.size() == 3
        assert cache.get("key1") == "value1"
        assert cache.get("key2") is None
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"

    def test_lru_eviction_order(self):
        """LRU淘汰应按访问顺序"""
        cache = EvaluationCache(ttl_seconds=60, max_size=3)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        cache.get("key2")
        cache.get("key1")

        cache.set("key4", "value4")

        assert cache.get("key3") is None
        assert cache.get("key4") == "value4"

    def test_max_size_zero_disables_cache(self):
        """max_size为0应禁用缓存"""
        cache = EvaluationCache(ttl_seconds=60, max_size=0)
        cache.set("key1", "value1")
        assert cache.size() == 0
        assert cache.get("key1") is None


class TestCacheStats:
    """缓存统计测试"""

    def test_stats_track_hits_and_misses(self, cache):
        """统计应追踪命中和未命中"""
        cache.set("key1", "value1")
        cache.get("key1")
        cache.get("key1")
        cache.get("nonexistent")

        stats = cache.get_stats()
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["evictions"] == 0

    def test_stats_evictions_count(self):
        """统计应追踪淘汰次数"""
        cache = EvaluationCache(ttl_seconds=60, max_size=2)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        stats = cache.get_stats()
        assert stats["evictions"] == 1

    def test_hit_rate_calculation(self, cache):
        """命中率应正确计算"""
        cache.set("key1", "value1")
        cache.get("key1")
        cache.get("nonexistent")

        stats = cache.get_stats()
        assert stats["hit_rate"] == 0.5

    def test_clear_resets_stats(self, cache):
        """清空缓存应重置统计"""
        cache.set("key1", "value1")
        cache.get("key1")
        cache.get("nonexistent")

        cache.clear()
        stats = cache.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["evictions"] == 0


class TestCacheThreadSafety:
    """线程安全测试"""

    def test_concurrent_access(self, cache):
        """并发访问应安全"""
        import threading

        def writer(cache, key, value):
            for i in range(10):
                cache.set(f"{key}_{i}", f"{value}_{i}")

        threads = []
        for i in range(5):
            t = threading.Thread(target=writer, args=(cache, f"thread_{i}", "value"))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert cache.size() == 50

    def test_concurrent_read_write(self, cache):
        """并发读写应安全"""
        import threading

        cache.set("shared_key", "initial")

        def reader(cache):
            for _ in range(10):
                _ = cache.get("shared_key")

        def writer(cache):
            for i in range(10):
                cache.set("shared_key", f"updated_{i}")

        threads = []
        for _ in range(3):
            threads.append(threading.Thread(target=reader, args=(cache,)))
            threads.append(threading.Thread(target=writer, args=(cache,)))

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        result = cache.get("shared_key")
        assert result is not None


class TestCachedDecorator:
    """缓存装饰器测试"""

    def test_decorator_caches_result(self):
        """装饰器应缓存结果"""
        from src.infra.cache import _cache

        _cache.clear()

        call_count = [0]

        @cached(key_prefix="test")
        def expensive_function(x):
            call_count[0] += 1
            return x * 2

        result1 = expensive_function(5)
        result2 = expensive_function(5)

        assert result1 == 10
        assert result2 == 10
        assert call_count[0] == 1

    def test_decorator_different_args(self):
        """装饰器应区分不同参数"""
        from src.infra.cache import _cache

        _cache.clear()

        call_count = [0]

        @cached(key_prefix="test")
        def expensive_function(x):
            call_count[0] += 1
            return x * 2

        expensive_function(5)
        expensive_function(10)

        assert call_count[0] == 2


class TestRedisIntegration:
    """Redis集成测试"""

    def test_get_redis_client(self):
        """get_redis_client应返回客户端"""
        with patch("src.infra.cache.redis.Redis") as mock_redis:
            mock_instance = MagicMock()
            mock_redis.return_value = mock_instance
            client = get_redis_client()
            assert client is not None
            mock_redis.assert_called_once()

    def test_get_redis(self):
        """get_redis应返回客户端"""
        client = get_redis()
        assert client is not None


class TestCacheIntegrationWithEvaluator:
    """与评估器集成测试"""

    def test_evaluation_result_cache(self, cache):
        """评估结果应能被缓存"""
        eval_result = {
            "case_id": "cache-001",
            "status": "passed",
            "response_data": {"score": 0.9},
        }
        cache.set("eval:cache-001", eval_result)
        cached_result = cache.get("eval:cache-001")
        assert cached_result is not None
        assert cached_result["case_id"] == "cache-001"
        assert cached_result["response_data"]["score"] == 0.9

    def test_cache_evaluation_with_ttl(self, short_ttl_cache):
        """带TTL的评估结果缓存"""
        eval_result = {"case_id": "cache-002", "score": 0.8}
        short_ttl_cache.set("eval:cache-002", eval_result)

        time.sleep(0.2)
        cached_result = short_ttl_cache.get("eval:cache-002")
        assert cached_result is None

    def test_cache_persistence_across_operations(self, cache):
        """缓存应在多次操作间保持持久"""
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        assert cache.get("key1") == "value1"
        assert cache.get("key2") == "value2"

        cache.invalidate("key1")
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"


class TestCacheEdgeCases:
    """边界情况测试"""

    def test_none_value_stored(self, cache):
        """None值应被存储"""
        cache.set("key1", None)
        result = cache.get("key1")
        assert result is None

    def test_empty_string_value(self, cache):
        """空字符串应被存储"""
        cache.set("key1", "")
        result = cache.get("key1")
        assert result == ""

    def test_large_value(self, cache):
        """大值应被存储"""
        large_value = "x" * 100000
        cache.set("large_key", large_value)
        result = cache.get("large_key")
        assert result == large_value

    def test_special_characters_key(self, cache):
        """特殊字符键应被存储"""
        cache.set("key with spaces", "value")
        cache.set("key/with/slashes", "value2")
        cache.set("key.with.dots", "value3")

        assert cache.get("key with spaces") == "value"
        assert cache.get("key/with/slashes") == "value2"
        assert cache.get("key.with.dots") == "value3"
