"""熔断�?Redis 持久化测�?""

import time
from unittest.mock import MagicMock, patch

import pytest

from src.distributed.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
)
from src.distributed.redis_cache import RedisCache


class TestCircuitBreakerRedisPersistence:
    """Redis 持久化测�?""

    def test_state_persistence_across_instances(self):
        """多个实例应共享熔断器状�?""
        mock_redis = MagicMock()
        mock_redis.is_connected = True
        mock_redis.get_circuit_breaker_state = MagicMock(return_value=None)
        mock_redis.set_circuit_breaker_state = MagicMock()
        mock_redis.increment_failure_count = MagicMock(return_value=1)
        mock_redis.increment_success_count = MagicMock(return_value=1)
        mock_redis.reset_counts = MagicMock()
        mock_redis.acquire_lock = MagicMock(return_value=True)
        mock_redis.release_lock = MagicMock()

        breaker1 = CircuitBreaker("shared", redis_client=mock_redis, auto_load_redis=False)
        breaker2 = CircuitBreaker("shared", redis_client=mock_redis, auto_load_redis=False)

        assert breaker1.state == CircuitState.CLOSED
        assert breaker2.state == CircuitState.CLOSED

        config = CircuitBreakerConfig(failure_threshold=2)
        breaker1 = CircuitBreaker(
            "shared-fail",
            config=config,
            redis_client=mock_redis,
            auto_load_redis=False,
            sync_interval=3600,
        )

        for _ in range(2):
            with pytest.raises(ValueError):
                breaker1.call_sync(lambda: (_ for _ in ()).throw(ValueError("fail")))

        assert breaker1.is_open is True
        mock_redis.set_circuit_breaker_state.assert_called()

    def test_distributed_lock_prevents_concurrent_transition(self):
        """分布式锁应防止多个实例同时修改状�?""
        mock_redis = MagicMock()
        mock_redis.is_connected = True
        mock_redis.get_circuit_breaker_state = MagicMock(return_value=None)
        mock_redis.set_circuit_breaker_state = MagicMock()
        mock_redis.increment_failure_count = MagicMock(return_value=1)
        mock_redis.increment_success_count = MagicMock(return_value=1)
        mock_redis.reset_counts = MagicMock()

        call_count = [0]

        def mock_acquire_lock(lock_key, timeout=5):
            call_count[0] += 1
            return call_count[0] == 1

        mock_redis.acquire_lock = mock_acquire_lock
        mock_redis.release_lock = MagicMock()

        breaker1 = CircuitBreaker(
            "lock-test",
            redis_client=mock_redis,
            auto_load_redis=False,
            sync_interval=3600,
        )
        breaker2 = CircuitBreaker(
            "lock-test",
            redis_client=mock_redis,
            auto_load_redis=False,
            sync_interval=3600,
        )

        config = CircuitBreakerConfig(failure_threshold=1)
        breaker1.config = config
        breaker2.config = config

        with pytest.raises(ValueError):
            breaker1.call_sync(lambda: (_ for _ in ()).throw(ValueError("fail")))

        with pytest.raises(ValueError):
            breaker2.call_sync(lambda: (_ for _ in ()).throw(ValueError("fail")))

        assert call_count[0] >= 1

    def test_atomic_failure_count_increment(self):
        """失败计数应使�?Redis 原子递增"""
        mock_redis = MagicMock()
        mock_redis.is_connected = True
        mock_redis.get_circuit_breaker_state = MagicMock(return_value=None)
        mock_redis.set_circuit_breaker_state = MagicMock()
        mock_redis.increment_failure_count = MagicMock(return_value=3)
        mock_redis.increment_success_count = MagicMock(return_value=1)
        mock_redis.reset_counts = MagicMock()
        mock_redis.acquire_lock = MagicMock(return_value=True)
        mock_redis.release_lock = MagicMock()

        breaker = CircuitBreaker(
            "atomic-test",
            redis_client=mock_redis,
            auto_load_redis=False,
            sync_interval=3600,
        )

        with pytest.raises(ValueError):
            breaker.call_sync(lambda: (_ for _ in ()).throw(ValueError("fail")))

        mock_redis.increment_failure_count.assert_called_with("atomic-test")

    def test_atomic_success_count_increment(self):
        """成功计数应使�?Redis 原子递增"""
        mock_redis = MagicMock()
        mock_redis.is_connected = True
        mock_redis.get_circuit_breaker_state = MagicMock(return_value=None)
        mock_redis.set_circuit_breaker_state = MagicMock()
        mock_redis.increment_failure_count = MagicMock(return_value=1)
        mock_redis.increment_success_count = MagicMock(return_value=1)
        mock_redis.reset_counts = MagicMock()

        breaker = CircuitBreaker(
            "success-atomic",
            redis_client=mock_redis,
            auto_load_redis=False,
            sync_interval=3600,
        )

        breaker.call_sync(lambda: "success")

        mock_redis.increment_success_count.assert_called_with("success-atomic")
        mock_redis.reset_counts.assert_called()

    def test_state_sync_from_redis(self):
        """应定期从 Redis 同步状�?""
        state_data = {
            "state": "open",
            "failure_count": 5,
            "success_count": 0,
            "last_failure_time": time.time(),
            "half_open_calls": 0,
            "stats": {
                "total_calls": 5,
                "successful_calls": 0,
                "failed_calls": 5,
                "rejected_calls": 0,
                "state_changes": 1,
                "last_state_change_time": time.time(),
            },
        }

        mock_redis = MagicMock()
        mock_redis.is_connected = True
        mock_redis.get_circuit_breaker_state = MagicMock(return_value=state_data)
        mock_redis.set_circuit_breaker_state = MagicMock()
        mock_redis.increment_failure_count = MagicMock(return_value=1)
        mock_redis.increment_success_count = MagicMock(return_value=1)
        mock_redis.reset_counts = MagicMock()

        breaker = CircuitBreaker(
            "sync-test",
            redis_client=mock_redis,
            auto_load_redis=False,
            sync_interval=0,
        )

        assert breaker.state == CircuitState.OPEN
        assert breaker.stats.total_calls == 5

    def test_sync_interval_throttling(self):
        """同步间隔应限制同步频�?""
        call_count = [0]
        mock_redis = MagicMock()
        mock_redis.is_connected = True

        def mock_get_state(breaker_name):
            call_count[0] += 1
            return None

        mock_redis.get_circuit_breaker_state = mock_get_state
        mock_redis.set_circuit_breaker_state = MagicMock()
        mock_redis.increment_failure_count = MagicMock(return_value=1)
        mock_redis.increment_success_count = MagicMock(return_value=1)
        mock_redis.reset_counts = MagicMock()

        breaker = CircuitBreaker(
            "throttle-test",
            redis_client=mock_redis,
            auto_load_redis=False,
            sync_interval=60.0,
        )

        for _ in range(5):
            _ = breaker.state

        assert call_count[0] == 1

    def test_redis_failure_degrade_to_memory(self):
        """Redis 不可用时应降级到内存存储"""
        mock_redis = MagicMock()
        mock_redis.is_connected = False

        breaker = CircuitBreaker(
            "degrade-test",
            redis_client=mock_redis,
            auto_load_redis=False,
            sync_interval=3600,
        )

        breaker.call_sync(lambda: "success")
        assert breaker.stats.successful_calls == 1

        with pytest.raises(ValueError):
            breaker.call_sync(lambda: (_ for _ in ()).throw(ValueError("fail")))
        assert breaker.stats.failed_calls == 1


class TestRedisCacheMemoryFallback:
    """Redis 缓存内存降级测试"""

    def test_set_and_get_without_redis(self):
        """�?Redis 时应使用内存缓存"""
        with patch("redis.Redis.from_url") as mock_from_url:
            mock_from_url.side_effect = Exception("Connection refused")
            cache = RedisCache()

            assert cache.is_connected is False

            cache.set("test_key", "test_value")
            result = cache.get("test_key")
            assert result == "test_value"

    def test_set_json_and_get_json_without_redis(self):
        """�?Redis 时应使用内存缓存存储 JSON"""
        with patch("redis.Redis.from_url") as mock_from_url:
            mock_from_url.side_effect = Exception("Connection refused")
            cache = RedisCache()

            data = {"key": "value", "number": 42}
            cache.set_json("json_key", data)
            result = cache.get_json("json_key")
            assert result == data

    def test_incr_without_redis(self):
        """�?Redis 时应使用内存缓存进行递增"""
        with patch("redis.Redis.from_url") as mock_from_url:
            mock_from_url.side_effect = Exception("Connection refused")
            cache = RedisCache()

            result1 = cache.incr("counter")
            assert result1 == 1

            result2 = cache.incr("counter")
            assert result2 == 2

    def test_acquire_lock_without_redis(self):
        """�?Redis 时应使用本地�?""
        with patch("redis.Redis.from_url") as mock_from_url:
            mock_from_url.side_effect = Exception("Connection refused")
            cache = RedisCache()

            acquired1 = cache.acquire_lock("test_lock")
            assert acquired1 is True

            acquired2 = cache.acquire_lock("test_lock")
            assert acquired2 is False

            cache.release_lock("test_lock")

            acquired3 = cache.acquire_lock("test_lock")
            assert acquired3 is True

    def test_health_check(self):
        """健康检查应正确检�?Redis 状�?""
        with patch("redis.Redis.from_url") as mock_from_url:
            mock_from_url.side_effect = Exception("Connection refused")
            cache = RedisCache()

            assert cache.health_check() is False

    def test_reconnect_attempt(self):
        """应定期尝试重新连�?""
        call_count = [0]
        with patch("redis.Redis.from_url") as mock_from_url:

            def mock_connect(*args, **kwargs):
                call_count[0] += 1
                raise Exception("Connection refused")

            mock_from_url.side_effect = mock_connect
            cache = RedisCache()

            assert cache.is_connected is False

            cache._reconnect_interval = 0
            _ = cache.is_connected

            assert call_count[0] >= 2
