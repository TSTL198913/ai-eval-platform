"""测试 distributed/circuit_breaker.py - 熔断器核心模块"""

import time
from unittest.mock import Mock

import pytest

from src.distributed.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerRegistry,
    CircuitState,
    circuit_breaker,
)


class TestCircuitBreakerConfig:
    """测试熔断器配置"""

    def test_default_config(self):
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.timeout_seconds == 30.0
        assert config.half_open_max_calls == 3
        assert config.success_threshold == 2

    def test_custom_config(self):
        config = CircuitBreakerConfig(
            failure_threshold=3,
            timeout_seconds=10.0,
            half_open_max_calls=1,
            success_threshold=1,
        )
        assert config.failure_threshold == 3
        assert config.timeout_seconds == 10.0
        assert config.half_open_max_calls == 1


class TestCircuitBreakerStateTransitions:
    """测试状态转换"""

    @pytest.fixture
    def cb(self):
        config = CircuitBreakerConfig(failure_threshold=3, timeout_seconds=1.0)
        return CircuitBreaker("test", config)

    def test_initial_state(self, cb):
        assert cb.state == CircuitState.CLOSED

    def test_closed_to_open(self, cb):
        for _ in range(3):
            cb._record_failure()
        assert cb.state == CircuitState.OPEN

    def test_open_to_half_open_after_timeout(self, cb):
        for _ in range(3):
            cb._record_failure()
        assert cb.state == CircuitState.OPEN
        cb._last_failure_time = time.time() - 2.0
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_to_closed_on_success(self, cb):
        for _ in range(3):
            cb._record_failure()
        cb._state = CircuitState.HALF_OPEN
        cb._last_failure_time = None
        for _ in range(2):
            cb._record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_to_open_on_failure(self, cb):
        for _ in range(3):
            cb._record_failure()
        cb._state = CircuitState.HALF_OPEN
        cb._last_failure_time = None
        cb._record_failure()
        assert cb.state == CircuitState.OPEN

    def test_success_count_half_open(self, cb):
        cb._state = CircuitState.HALF_OPEN
        cb._success_count = 0
        cb._record_success()
        assert cb._success_count == 1

    def test_failure_count_reset(self, cb):
        cb._record_failure()
        cb._record_failure()
        assert cb._failure_count == 2
        cb._record_success()
        assert cb._failure_count == 0


class TestCircuitBreakerCall:
    """测试熔断器调用"""

    @pytest.fixture
    def cb(self):
        config = CircuitBreakerConfig(failure_threshold=3, timeout_seconds=1.0)
        return CircuitBreaker("test_call", config)

    async def test_successful_call(self, cb):
        async def any_func():
            return "success"

        result = await cb.call(any_func)
        assert result == "success"
        assert cb.stats.successful_calls == 1

    async def test_failed_call(self, cb):
        async def failing_func():
            raise ValueError("test error")

        with pytest.raises(ValueError):
            await cb.call(failing_func)
        assert cb.stats.failed_calls == 1

    async def test_open_circuit_rejects(self, cb):
        for _ in range(3):
            cb._record_failure()
        assert cb.state == CircuitState.OPEN

        async def any_func():
            return "result"

        with pytest.raises(CircuitBreakerError):
            await cb.call(any_func)
        assert cb.stats.rejected_calls == 1

    async def test_half_open_probe_succeeds(self, cb):
        for _ in range(3):
            cb._record_failure()
        cb._state = CircuitState.HALF_OPEN
        cb._last_failure_time = None
        cb._half_open_calls = 0

        async def success_func():
            return "ok"

        result = await cb.call(success_func)
        assert result == "ok"

    async def test_half_open_probe_fails(self, cb):
        for _ in range(3):
            cb._record_failure()
        cb._state = CircuitState.HALF_OPEN
        cb._last_failure_time = None
        cb._half_open_calls = 0

        async def fail_func():
            raise RuntimeError("fail")

        with pytest.raises(RuntimeError):
            await cb.call(fail_func)
        assert cb.state == CircuitState.OPEN


class TestCircuitBreakerStats:
    """测试熔断器统计信息"""

    def test_stats_initialization(self):
        cb = CircuitBreaker("stats_test")
        stats = cb.get_stats()
        assert stats["name"] == "stats_test"
        assert stats["state"] == "closed"
        assert stats["total_calls"] == 0
        assert stats["successful_calls"] == 0
        assert stats["failed_calls"] == 0
        assert stats["rejected_calls"] == 0

    def test_stats_after_calls(self):
        cb = CircuitBreaker("stats_test")
        cb._record_failure()
        cb._record_failure()
        cb._record_success()
        stats = cb.get_stats()
        assert stats["failed_calls"] == 2
        assert stats["successful_calls"] == 1


class TestCircuitBreakerReset:
    """测试手动重置"""

    def test_reset(self):
        cb = CircuitBreaker("reset_test")
        cb._record_failure()
        cb._record_failure()
        cb._state = CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 0
        assert cb._success_count == 0
        assert cb._last_failure_time is None


class TestCircuitBreakerDecorator:
    """测试熔断器装饰器"""

    async def test_decorator_success(self):
        breaker = circuit_breaker("decorator_test")

        @breaker
        async def my_func():
            return "decorated"

        result = await my_func()
        assert result == "decorated"

    async def test_decorator_failure(self):
        breaker = circuit_breaker("decorator_fail")

        @breaker
        async def my_func():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            await my_func()


class TestCircuitBreakerRegistry:
    """测试熔断器注册中心"""

    def test_singleton_via_get_instance(self):
        r1 = CircuitBreakerRegistry.get_instance()
        r2 = CircuitBreakerRegistry.get_instance()
        assert r1 is r2

    def test_get_or_create(self):
        registry = CircuitBreakerRegistry.get_instance()
        cb1 = registry.get_or_create("test_reg")
        cb2 = registry.get_or_create("test_reg")
        assert cb1 is cb2
        assert cb1.name == "test_reg"

    def test_get(self):
        registry = CircuitBreakerRegistry.get_instance()
        registry.get_or_create("get_test")
        cb = registry.get("get_test")
        assert cb is not None
        assert cb.name == "get_test"
        assert registry.get("nonexistent") is None

    def test_list_breakers(self):
        registry = CircuitBreakerRegistry.get_instance()
        registry.get_or_create("list1")
        registry.get_or_create("list2")
        breakers = registry.list_breakers()
        assert "list1" in breakers
        assert "list2" in breakers

    def test_all_stats(self):
        registry = CircuitBreakerRegistry.get_instance()
        registry.get_or_create("stats1")
        stats = registry.all_stats()
        assert "stats1" in stats


class TestCircuitBreakerRedisPersistence:
    """测试熔断器 Redis 持久化"""

    def test_init_with_redis_client(self):
        """测试初始化时加载 Redis 状态"""
        mock_redis = Mock()
        mock_redis.get.return_value = None  # Redis 中无数据

        cb = CircuitBreaker("redis_test", redis_client=mock_redis)
        assert cb._redis_client == mock_redis
        assert cb._redis_key == "circuit_breaker:redis_test"

    def test_load_state_from_redis(self):
        """测试从 Redis 加载状态"""
        import json
        import time

        mock_redis = Mock()
        # 使用当前时间，确保状态不会被超时转换
        current_time = time.time()
        mock_redis.get.return_value = json.dumps({
            "state": "open",
            "failure_count": 5,
            "success_count": 0,
            "last_failure_time": current_time,  # 使用当前时间
            "half_open_calls": 0,
            "stats": {
                "total_calls": 10,
                "successful_calls": 5,
                "failed_calls": 5,
                "rejected_calls": 0,
                "state_changes": 1,
                "last_state_change_time": current_time,
            },
        })

        cb = CircuitBreaker("load_test", redis_client=mock_redis)
        # 由于 last_failure_time 是当前时间，状态应该保持 OPEN
        assert cb._state == CircuitState.OPEN  # 检查内部状态
        assert cb._failure_count == 5
        assert cb.stats.total_calls == 10

    def test_save_state_to_redis_on_transition(self):
        """测试状态转换时保存到 Redis"""
        import json

        mock_redis = Mock()
        mock_redis.get.return_value = None
        mock_redis.set = Mock()

        config = CircuitBreakerConfig(failure_threshold=2)
        cb = CircuitBreaker("save_test", config=config, redis_client=mock_redis)

        # 触发状态转换
        cb._record_failure()
        cb._record_failure()

        assert cb.state == CircuitState.OPEN
        mock_redis.set.assert_called()

        # 验证保存的数据
        call_args = mock_redis.set.call_args
        saved_data = json.loads(call_args[0][1])
        assert saved_data["state"] == "open"
        assert saved_data["failure_count"] == 2

    def test_reset_saves_to_redis(self):
        """测试重置时保存到 Redis"""
        import json

        mock_redis = Mock()
        mock_redis.get.return_value = None
        mock_redis.set = Mock()

        cb = CircuitBreaker("reset_redis_test", redis_client=mock_redis)
        cb._state = CircuitState.OPEN
        cb._failure_count = 5

        cb.reset()

        mock_redis.set.assert_called()
        saved_data = json.loads(mock_redis.set.call_args[0][1])
        assert saved_data["state"] == "closed"
        assert saved_data["failure_count"] == 0

    def test_redis_persistence_disabled(self):
        """测试无 Redis 客户端时不持久化"""
        cb = CircuitBreaker("no_redis_test", redis_client=None)
        cb._record_failure()

        # 无 Redis 客户端时不应抛出异常
        cb._save_state_to_redis()
        cb._load_state_from_redis()

    def test_redis_error_handling(self):
        """测试 Redis 错误处理"""
        mock_redis = Mock()
        mock_redis.get.side_effect = Exception("Redis connection error")
        mock_redis.set.side_effect = Exception("Redis write error")

        # 初始化时 Redis 错误不应影响熔断器创建
        cb = CircuitBreaker("error_test", redis_client=mock_redis)
        assert cb.state == CircuitState.CLOSED

        # 状态转换时 Redis 错误不应影响熔断器功能
        cb._record_failure()
        cb._record_failure()
        cb._record_failure()
        cb._record_failure()
        cb._record_failure()
        assert cb._failure_count == 5
