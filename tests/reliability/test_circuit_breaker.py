"""分布式熔断器测试"""

import time
from unittest.mock import MagicMock

import pytest

from src.distributed.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerRegistry,
    CircuitState,
)


class TestCircuitBreakerBasic:
    """熔断器基础测试"""

    @pytest.fixture
    def breaker(self):
        return CircuitBreaker(
            "test-breaker",
            config=CircuitBreakerConfig(
                failure_threshold=3,
                success_threshold=2,
                timeout_seconds=10.0,
            ),
        )

    def test_initial_state_closed(self, breaker):
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_success_keeps_closed(self, breaker):
        for _ in range(5):
            result = await breaker.call(lambda: "success")
            assert result == "success"
            assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_failure_threshold_triggers_open(self, breaker):
        for _ in range(3):
            with pytest.raises(Exception):
                await breaker.call(lambda: 1 / 0)
        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_open_state_blocks_requests(self, breaker):
        for _ in range(3):
            with pytest.raises(Exception):
                await breaker.call(lambda: 1 / 0)
        assert breaker.state == CircuitState.OPEN
        with pytest.raises(CircuitBreakerError):
            await breaker.call(lambda: "should_fail")

    def test_timeout_triggers_half_open(self, breaker):
        breaker._state = CircuitState.OPEN
        breaker._last_failure_time = time.time() - 60.0
        assert breaker.state == CircuitState.HALF_OPEN


class TestCircuitBreakerStateTransitions:
    """熔断器状态转换测试"""

    @pytest.fixture
    def breaker(self):
        return CircuitBreaker(
            "state-test",
            config=CircuitBreakerConfig(
                failure_threshold=2,
                success_threshold=2,
                timeout_seconds=0.1,
            ),
        )

    @pytest.mark.asyncio
    async def test_closed_to_open(self, breaker):
        with pytest.raises(Exception):
            await breaker.call(lambda: 1 / 0)
        with pytest.raises(Exception):
            await breaker.call(lambda: 1 / 0)
        assert breaker.state == CircuitState.OPEN

    def test_open_to_half_open(self, breaker):
        breaker._state = CircuitState.OPEN
        breaker._last_failure_time = time.time() - 60.0
        assert breaker.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_to_closed(self, breaker):
        breaker._state = CircuitState.HALF_OPEN
        await breaker.call(lambda: "success")
        await breaker.call(lambda: "success")
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_to_open(self, breaker):
        breaker._state = CircuitState.HALF_OPEN
        with pytest.raises(Exception):
            await breaker.call(lambda: 1 / 0)
        assert breaker.state == CircuitState.OPEN


class TestCircuitBreakerStats:
    """熔断器统计测试"""

    @pytest.fixture
    def breaker(self):
        return CircuitBreaker(
            "stats-test",
            config=CircuitBreakerConfig(
                failure_threshold=5,
                success_threshold=2,
                timeout_seconds=10.0,
            ),
        )

    @pytest.mark.asyncio
    async def test_stats_count_calls(self, breaker):
        await breaker.call(lambda: "success")
        await breaker.call(lambda: "success")
        assert breaker.stats.total_calls == 2
        assert breaker.stats.successful_calls == 2
        assert breaker.stats.failed_calls == 0

    @pytest.mark.asyncio
    async def test_stats_count_failures(self, breaker):
        with pytest.raises(Exception):
            await breaker.call(lambda: 1 / 0)
        assert breaker.stats.total_calls == 1
        assert breaker.stats.successful_calls == 0
        assert breaker.stats.failed_calls == 1

    @pytest.mark.asyncio
    async def test_stats_rejected_calls(self, breaker):
        for _ in range(5):
            with pytest.raises(Exception):
                await breaker.call(lambda: 1 / 0)
        with pytest.raises(CircuitBreakerError):
            await breaker.call(lambda: "should_fail")
        assert breaker.stats.rejected_calls == 1


class TestCircuitBreakerEdgeCases:
    """熔断器边界情况测试"""

    @pytest.fixture
    def breaker(self):
        return CircuitBreaker(
            "edge-test",
            config=CircuitBreakerConfig(
                failure_threshold=1,
                success_threshold=1,
                timeout_seconds=0.1,
            ),
        )

    @pytest.mark.asyncio
    async def test_immediate_open(self, breaker):
        with pytest.raises(Exception):
            await breaker.call(lambda: 1 / 0)
        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_immediate_close(self, breaker):
        breaker._state = CircuitState.HALF_OPEN
        await breaker.call(lambda: "success")
        assert breaker.state == CircuitState.CLOSED


class TestCircuitBreakerConfig:
    """熔断器配置测试"""

    def test_default_config(self):
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.success_threshold == 2
        assert config.timeout_seconds == 30.0
        assert config.half_open_max_calls == 3

    def test_custom_config(self):
        config = CircuitBreakerConfig(
            failure_threshold=10,
            success_threshold=5,
            timeout_seconds=60.0,
            half_open_max_calls=5,
        )
        assert config.failure_threshold == 10
        assert config.success_threshold == 5
        assert config.timeout_seconds == 60.0
        assert config.half_open_max_calls == 5


class TestCircuitBreakerRedisPersistence:
    """熔断器Redis持久化测试"""

    @pytest.fixture
    def mock_redis(self):
        mock = MagicMock()
        mock.get = MagicMock(return_value=None)
        mock.set = MagicMock()
        return mock

    @pytest.fixture
    def breaker(self, mock_redis):
        return CircuitBreaker("redis-test", redis_client=mock_redis)

    @pytest.mark.asyncio
    async def test_save_state_on_transition(self, breaker, mock_redis):
        with pytest.raises(Exception):
            await breaker.call(lambda: 1 / 0)
        with pytest.raises(Exception):
            await breaker.call(lambda: 1 / 0)
        with pytest.raises(Exception):
            await breaker.call(lambda: 1 / 0)
        with pytest.raises(Exception):
            await breaker.call(lambda: 1 / 0)
        with pytest.raises(Exception):
            await breaker.call(lambda: 1 / 0)
        mock_redis.set.assert_called()

    def test_load_state_from_redis(self, mock_redis):
        import json

        mock_redis.get = MagicMock(
            return_value=json.dumps(
                {
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
            )
        )
        breaker = CircuitBreaker("redis-load", redis_client=mock_redis)
        assert breaker._state == CircuitState.OPEN
        assert breaker.stats.total_calls == 5


class TestCircuitBreakerRegistry:
    """熔断器注册中心测试"""

    def test_get_instance(self):
        registry1 = CircuitBreakerRegistry.get_instance()
        registry2 = CircuitBreakerRegistry.get_instance()
        assert registry1 is registry2

    def test_get_or_create(self):
        registry = CircuitBreakerRegistry.get_instance()
        breaker = registry.get_or_create("test-registry")
        assert breaker.name == "test-registry"
        breaker2 = registry.get_or_create("test-registry")
        assert breaker is breaker2

    def test_get(self):
        registry = CircuitBreakerRegistry.get_instance()
        breaker = registry.get_or_create("test-get")
        assert registry.get("test-get") is breaker
        assert registry.get("nonexistent") is None

    def test_list_breakers(self):
        registry = CircuitBreakerRegistry.get_instance()
        registry.get_or_create("breaker1")
        registry.get_or_create("breaker2")
        breakers = registry.list_breakers()
        assert "breaker1" in breakers
        assert "breaker2" in breakers

    def test_all_stats(self):
        registry = CircuitBreakerRegistry.get_instance()
        registry.get_or_create("stats-breaker")
        stats = registry.all_stats()
        assert "stats-breaker" in stats


class TestCircuitBreakerReset:
    """熔断器重置测试"""

    @pytest.fixture
    def breaker(self):
        return CircuitBreaker(
            "reset-test",
            config=CircuitBreakerConfig(
                failure_threshold=2,
                success_threshold=2,
                timeout_seconds=10.0,
            ),
        )

    @pytest.mark.asyncio
    async def test_reset_returns_to_closed(self, breaker):
        with pytest.raises(Exception):
            await breaker.call(lambda: 1 / 0)
        with pytest.raises(Exception):
            await breaker.call(lambda: 1 / 0)
        assert breaker.state == CircuitState.OPEN
        breaker.reset()
        assert breaker.state == CircuitState.CLOSED
        assert breaker._failure_count == 0


class TestCircuitBreakerAsyncFunction:
    """熔断器异步函数测试"""

    @pytest.fixture
    def breaker(self):
        return CircuitBreaker(
            "async-test",
            config=CircuitBreakerConfig(
                failure_threshold=2,
                success_threshold=2,
                timeout_seconds=10.0,
            ),
        )

    @pytest.mark.asyncio
    async def test_async_function_success(self, breaker):
        async def async_func():
            return "async_result"

        result = await breaker.call(async_func)
        assert result == "async_result"

    @pytest.mark.asyncio
    async def test_async_function_failure(self, breaker):
        async def async_func():
            raise Exception("async_error")

        with pytest.raises(Exception):
            await breaker.call(async_func)
        assert breaker._failure_count == 1
