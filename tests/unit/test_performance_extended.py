import pytest
import asyncio
import time
from unittest.mock import MagicMock, patch

from src.infra.performance import (
    CacheConfig,
    CacheEntry,
    SegmentLock,
    LRUCache,
)


class TestCacheConfig:
    def test_default_config(self):
        config = CacheConfig()
        assert config.max_size == 1000
        assert config.ttl_seconds == 300.0
        assert config.eviction_policy == 'lru'
        assert config.segment_count == 16

    def test_custom_config(self):
        config = CacheConfig(
            max_size=500,
            ttl_seconds=60.0,
            eviction_policy='lfu',
            segment_count=8
        )
        assert config.max_size == 500
        assert config.ttl_seconds == 60.0
        assert config.eviction_policy == 'lfu'
        assert config.segment_count == 8


class TestCacheEntry:
    def test_entry_creation(self):
        entry = CacheEntry(value='test_value')
        assert entry.value == 'test_value'
        assert entry.hits == 0
        assert entry.key == ''

    def test_entry_expiration(self):
        entry = CacheEntry(value='test', expires_at=time.time() - 1)
        assert entry.is_expired() is True

    def test_entry_not_expired(self):
        entry = CacheEntry(value='test', expires_at=time.time() + 100)
        assert entry.is_expired() is False

    def test_entry_increment_hit(self):
        entry = CacheEntry(value='test')
        entry.increment_hit()
        assert entry.hits == 1
        entry.increment_hit()
        assert entry.hits == 2

    def test_entry_post_init(self):
        entry = CacheEntry(value='test')
        assert entry.expires_at > entry.created_at


class TestSegmentLock:
    def test_lock_initialization(self):
        lock = SegmentLock(segment_count=16)
        assert lock._segment_count == 16
        assert len(lock._locks) == 16

    def test_get_lock(self):
        lock = SegmentLock(segment_count=4)
        lock1 = lock.get_lock('key1')
        lock2 = lock.get_lock('key2')
        assert lock1 is not None
        assert lock2 is not None

    def test_get_all_locks(self):
        lock = SegmentLock(segment_count=8)
        all_locks = lock.get_all_locks()
        assert len(all_locks) == 8

    def test_lock_consistency(self):
        lock = SegmentLock(segment_count=4)
        lock1 = lock.get_lock('same_key')
        lock2 = lock.get_lock('same_key')
        assert lock1 == lock2


class TestLRUCache:
    def test_cache_initialization(self):
        cache = LRUCache()
        assert cache._config is not None
        assert len(cache._cache) == 0

    def test_cache_with_custom_config(self):
        config = CacheConfig(max_size=100)
        cache = LRUCache(config)
        assert cache._config.max_size == 100

    @pytest.mark.asyncio
    async def test_cache_set_and_get(self):
        cache = LRUCache()
        await cache.set('key1', 'value1')
        result = await cache.get('key1')
        assert result == 'value1'

    @pytest.mark.asyncio
    async def test_cache_get_missing_key(self):
        cache = LRUCache()
        result = await cache.get('nonexistent')
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_delete(self):
        cache = LRUCache()
        await cache.set('key1', 'value1')
        await cache.delete('key1')
        result = await cache.get('key1')
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_eviction(self):
        config = CacheConfig(max_size=2)
        cache = LRUCache(config)
        await cache.set('key1', 'value1')
        await cache.set('key2', 'value2')
        await cache.set('key3', 'value3')
        result = await cache.get('key1')
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_ttl_expiration(self):
        config = CacheConfig(ttl_seconds=0.1)
        cache = LRUCache(config)
        await cache.set('key1', 'value1', ttl=0.1)
        await asyncio.sleep(0.2)
        result = await cache.get('key1')
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_update_existing_key(self):
        cache = LRUCache()
        await cache.set('key1', 'value1')
        await cache.set('key1', 'value2')
        result = await cache.get('key1')
        assert result == 'value2'

    @pytest.mark.asyncio
    async def test_cache_stats(self):
        cache = LRUCache()
        await cache.set('key1', 'value1')
        await cache.get('key1')
        await cache.get('nonexistent')
        stats = cache._stats
        assert stats['hits'] == 1
        assert stats['misses'] == 1
