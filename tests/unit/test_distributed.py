"""
分布式组件单元测试
"""

import asyncio
import time
from unittest.mock import MagicMock

import pytest

from src.distributed.lock import DistributedLock, LockState
from src.distributed.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitState,
)
from src.distributed.rate_limiter import (
    RateLimitConfig,
    TokenBucket,
    RateLimitResult,
)


class TestDistributedLock:
    """分布式锁测试"""

    def test_lock_acquire_success(self):
        """测试获取锁成功"""
        mock_redis = MagicMock()
        mock_redis.set.return_value = True
        
        lock = DistributedLock(mock_redis, "test_key", ttl_seconds=30.0)
        result = lock.acquire()
        
        assert result.state == LockState.ACQUIRED
        assert result.lock_key == "eval:lock:test_key"
        assert result.ttl_ms == 30000
        mock_redis.set.assert_called_once()

    def test_lock_acquire_failure(self):
        """测试获取锁失败"""
        mock_redis = MagicMock()
        mock_redis.set.return_value = False
        
        lock = DistributedLock(mock_redis, "test_key", retry_times=1)
        result = lock.acquire()
        
        assert result.state == LockState.NOT_ACQUIRED

    def test_lock_release(self):
        """测试释放锁"""
        mock_redis = MagicMock()
        mock_redis.set.return_value = True
        mock_redis.eval.return_value = 1
        
        lock = DistributedLock(mock_redis, "test_key")
        lock.acquire()
        released = lock.release()
        
        assert released is True
        mock_redis.eval.assert_called_once()

    def test_lock_context_manager(self):
        """测试上下文管理器"""
        mock_redis = MagicMock()
        mock_redis.set.return_value = True
        mock_redis.eval.return_value = 1
        
        lock = DistributedLock(mock_redis, "test_key")
        
        with lock:
            assert lock.is_acquired
        
        mock_redis.eval.assert_called_once()

    def test_lock_extend(self):
        """测试延长锁的 TTL"""
        mock_redis = MagicMock()
        mock_redis.set.return_value = True
        mock_redis.eval.side_effect = [1, 1]  # release 和 extend
        
        lock = DistributedLock(mock_redis, "test_key")
        lock.acquire()
        
        # 先 release 再测试 extend
        lock.release()
        mock_redis.eval.side_effect = [1, 1]
        
        lock.acquire()
        extended = lock.extend(60.0)
        
        assert extended is True


class TestCircuitBreaker:
    """熔断器测试"""

    def test_circuit_breaker_initial_state(self):
        """测试熔断器初始状态"""
        cb = CircuitBreaker("test_service")
        assert cb.state == CircuitState.CLOSED
        assert cb.is_closed

    def test_circuit_breaker_open_on_failures(self):
        """测试连续失败后打开熔断器"""
        cb = CircuitBreaker(
            "test_service",
            CircuitBreakerConfig(failure_threshold=3),
        )
        
        # 记录失败
        cb._record_failure()
        assert cb.state == CircuitState.CLOSED
        
        cb._record_failure()
        assert cb.state == CircuitState.CLOSED
        
        cb._record_failure()
        assert cb.state == CircuitState.OPEN

    def test_circuit_breaker_half_open_after_timeout(self):
        """测试超时后进入半开状态"""
        cb = CircuitBreaker(
            "test_service",
            CircuitBreakerConfig(failure_threshold=1, timeout_seconds=0.1),
        )
        
        # 触发熔断
        cb._record_failure()
        assert cb.state == CircuitState.OPEN
        
        # 等待超时
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

    def test_circuit_breaker_rejects_when_open(self):
        """测试熔断器打开时拒绝调用"""
        
        cb = CircuitBreaker(
            "test_service",
            CircuitBreakerConfig(failure_threshold=1, timeout_seconds=60),
        )
        
        # 触发熔断
        cb._record_failure()
        assert cb.is_open
        
        # 尝试调用
        async def dummy_func():
            return "success"
        
        with pytest.raises(CircuitBreakerError):
            asyncio.run(cb.call(dummy_func))

    def test_circuit_breaker_success_resets(self):
        """测试成功后关闭熔断器"""
        
        cb = CircuitBreaker(
            "test_service",
            CircuitBreakerConfig(
                failure_threshold=1,
                success_threshold=1,
                timeout_seconds=0.05,
            ),
        )
        
        # 初始状态是 CLOSED
        assert cb.state == CircuitState.CLOSED
        
        # 触发熔断 - 失败一次就打开
        cb._record_failure()
        assert cb._state == CircuitState.OPEN, f"Expected OPEN but got {cb._state}"
        
        # 等待进入半开状态
        time.sleep(0.1)
        # 在 OPEN 状态下超时后会返回 HALF_OPEN
        assert cb.state == CircuitState.HALF_OPEN
        
        # 在 HALF_OPEN 状态下记录成功应该转换到 CLOSED
        cb._record_success()
        # 验证状态转换
        assert cb._state == CircuitState.CLOSED, f"After success, expected CLOSED but got {cb._state}"

    def test_circuit_breaker_stats(self):
        """测试统计信息"""
        cb = CircuitBreaker("test_service")
        
        cb._record_success()
        cb._record_failure()
        cb._record_failure()
        
        stats = cb.get_stats()
        
        assert stats["total_calls"] == 3
        assert stats["successful_calls"] == 1
        assert stats["failed_calls"] == 2
        assert stats["name"] == "test_service"


class TestTokenBucket:
    """令牌桶测试"""

    def test_token_bucket_initial_full(self):
        """测试初始状态桶满"""
        mock_redis = MagicMock()
        mock_redis.register_script.return_value = MagicMock(
            return_value=[1, 99]  # allowed=1, remaining=99
        )
        
        config = RateLimitConfig(max_tokens=100, refill_rate=10)
        bucket = TokenBucket(mock_redis, "test_limit", config)
        
        result = bucket.allow()
        
        assert result.allowed is True
        assert result.remaining_tokens == 99

    def test_token_bucket_rejected(self):
        """测试被限流"""
        mock_redis = MagicMock()
        mock_redis.register_script.return_value = MagicMock(
            return_value=[0, 0]  # allowed=0, remaining=0
        )
        
        config = RateLimitConfig(max_tokens=100, refill_rate=10)
        bucket = TokenBucket(mock_redis, "test_limit", config)
        
        result = bucket.allow()
        
        assert result.allowed is False
        assert result.retry_after_ms is not None

    def test_token_bucket_multiple_tokens(self):
        """测试消耗多个令牌"""
        mock_redis = MagicMock()
        mock_redis.register_script.return_value = MagicMock(
            return_value=[1, 95]  # allowed=1, remaining=95
        )
        
        config = RateLimitConfig(max_tokens=100, refill_rate=10)
        bucket = TokenBucket(mock_redis, "test_limit", config)
        
        result = bucket.allow(tokens=5)
        
        assert result.allowed is True


class TestRateLimitResult:
    """限流结果测试"""

    def test_rate_limit_result_allowed(self):
        """测试允许的结果"""
        result = RateLimitResult(
            allowed=True,
            remaining_tokens=50,
            retry_after_ms=None,
            limit_key="test",
        )
        
        assert result.allowed is True
        assert result.remaining_tokens == 50
        assert result.retry_after_ms is None

    def test_rate_limit_result_rejected(self):
        """测试拒绝的结果"""
        result = RateLimitResult(
            allowed=False,
            remaining_tokens=0,
            retry_after_ms=100,
            limit_key="test",
        )
        
        assert result.allowed is False
        assert result.remaining_tokens == 0
        assert result.retry_after_ms == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
