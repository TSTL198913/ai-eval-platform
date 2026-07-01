"""
分布式模块集成测试
测试目标：验证分布式锁、限流器、消息队列和Redis缓存的完整集成流程
"""

import asyncio
import time
from unittest.mock import MagicMock

import pytest

from src.distributed.lock import DistributedLock, LockState, distributed_lock
from src.distributed.rate_limiter import (
    MultiDimensionRateLimiter,
    RateLimitConfig,
    RateLimitStrategy,
    RateLimiter,
    TokenBucket,
)
from src.distributed.queue import (
    BaseQueue,
    MessagePriority,
    QueueConfig,
    QueueMessage,
    QueueType,
    RedisListQueue,
    create_queue,
)
from src.distributed.redis_cache import RedisCache


@pytest.fixture
def mock_redis():
    """Mock Redis客户端"""
    redis = MagicMock()
    redis.set.return_value = True
    redis.get.return_value = None
    redis.delete.return_value = 1
    redis.exists.return_value = False
    redis.setnx.return_value = True
    redis.eval.return_value = 1
    redis.lpush.return_value = 1
    redis.brpoplpush.return_value = None
    redis.llen.return_value = 0
    redis.lrem.return_value = 1
    redis.hmget.return_value = [None, None]
    redis.hmset.return_value = True
    redis.expire.return_value = True
    return redis


class TestDistributedLockIntegration:
    """分布式锁集成测试"""

    def test_distributed_lock_acquire_release(self, mock_redis):
        """分布式锁应能正确获取和释放"""
        lock = DistributedLock(mock_redis, "test-resource")

        result = lock.acquire()
        assert result.state == LockState.ACQUIRED
        assert lock.is_acquired is True

        released = lock.release()
        assert released is True
        assert lock.is_acquired is False

    def test_distributed_lock_context_manager(self, mock_redis):
        """分布式锁应支持上下文管理器"""
        with DistributedLock(mock_redis, "context-lock") as lock:
            assert lock.is_acquired is True
            mock_redis.set.assert_called_once()

        assert lock.is_acquired is False
        assert mock_redis.eval.call_count >= 1

    def test_distributed_lock_fail_to_acquire(self, mock_redis):
        """分布式锁应在获取失败时返回NOT_ACQUIRED"""
        mock_redis.set.return_value = None

        lock = DistributedLock(mock_redis, "locked-resource", retry_times=1)
        result = lock.acquire()

        assert result.state == LockState.NOT_ACQUIRED

    def test_distributed_lock_extend(self, mock_redis):
        """分布式锁应能延长TTL"""
        lock = DistributedLock(mock_redis, "extend-lock")
        lock.acquire()

        extended = lock.extend(10)
        assert extended is True
        mock_redis.eval.assert_called()

    def test_distributed_lock_decorator(self, mock_redis):
        """分布式锁便捷函数应正确工作"""
        acquired = [False]

        try:
            with distributed_lock(mock_redis, "decorator-lock"):
                acquired[0] = True
            assert acquired[0] is True
        except RuntimeError:
            mock_redis.set.return_value = True
            with distributed_lock(mock_redis, "decorator-lock"):
                acquired[0] = True
            assert acquired[0] is True


class TestRateLimiterIntegration:
    """限流器集成测试"""

    def test_token_bucket_allow(self, mock_redis):
        """令牌桶应允许请求"""
        bucket = TokenBucket(mock_redis, "user-123")
        result = bucket.allow()

        assert result.allowed is True
        assert result.remaining_tokens <= 100

    def test_token_bucket_refuse_when_empty(self, mock_redis):
        """令牌桶应在令牌耗尽时拒绝请求"""
        mock_redis.hmget.return_value = ["0", str(time.time())]
        mock_redis.register_script.return_value.return_value = [0, 0]
        bucket = TokenBucket(mock_redis, "empty-bucket")
        bucket._script = mock_redis.register_script.return_value

        result = bucket.allow()

        assert result.allowed is False
        assert result.retry_after_ms is not None

    def test_rate_limiter_factory(self, mock_redis):
        """限流器工厂应正确创建不同类型的限流器"""
        limiter = RateLimiter(mock_redis, strategy=RateLimitStrategy.TOKEN_BUCKET)
        bucket = limiter.create_limiter("test-key")

        assert isinstance(bucket, TokenBucket)

    def test_multi_dimension_rate_limiter(self, mock_redis):
        """多维度限流器应同时检查多个维度"""
        limiter = MultiDimensionRateLimiter(mock_redis)

        allowed, failed = limiter.is_allowed(user_id="user-001", ip="192.168.1.1")
        assert allowed is True

    def test_multi_dimension_rate_limiter_rejected(self, mock_redis):
        """多维度限流器应在任意维度超限时拒绝"""
        mock_redis.hmget.return_value = ["0", str(time.time())]
        mock_redis.register_script.return_value.return_value = [0, 0]
        limiter = MultiDimensionRateLimiter(mock_redis)

        allowed, failed = limiter.is_allowed(user_id="rate-limited-user")
        assert allowed is False
        assert failed is not None


class TestQueueIntegration:
    """消息队列集成测试"""

    def test_redis_list_queue_publish(self, mock_redis):
        """Redis队列应能发布消息"""
        config = QueueConfig(queue_name="test-queue")
        queue = RedisListQueue(mock_redis, config)

        message = QueueMessage(
            message_id="msg-001",
            payload={"task": "evaluate", "id": "eval-001"},
        )

        async def test_publish():
            result = await queue.publish(message)
            assert result is True
            mock_redis.lpush.assert_called_once()

        asyncio.run(test_publish())

    def test_redis_list_queue_ack(self, mock_redis):
        """Redis队列应能ACK消息"""
        config = QueueConfig(queue_name="test-queue")
        queue = RedisListQueue(mock_redis, config)

        message = QueueMessage(
            message_id="msg-002",
            payload={"task": "evaluate", "id": "eval-002"},
        )

        async def test_ack():
            await queue.ack(message)
            mock_redis.lrem.assert_called_once()

        asyncio.run(test_ack())

    def test_redis_list_queue_nack_requeue(self, mock_redis):
        """Redis队列应能NACK并重新投递消息"""
        config = QueueConfig(queue_name="test-queue")
        queue = RedisListQueue(mock_redis, config)

        message = QueueMessage(
            message_id="msg-003",
            payload={"task": "evaluate", "id": "eval-003"},
            retry_count=0,
            max_retries=3,
        )

        async def test_nack():
            await queue.nack(message, requeue=True)
            assert message.retry_count == 1

        asyncio.run(test_nack())

    def test_queue_factory_create_redis_list(self, mock_redis):
        """队列工厂应能创建Redis队列"""
        config = QueueConfig(queue_type=QueueType.REDIS_LIST, queue_name="factory-queue")
        queue = create_queue(QueueType.REDIS_LIST, config, redis_client=mock_redis)

        assert isinstance(queue, RedisListQueue)
        assert isinstance(queue, BaseQueue)

    def test_queue_message_serialization(self):
        """队列消息应能正确序列化和反序列化"""
        message = QueueMessage(
            message_id="serial-001",
            payload={"test": "data"},
            priority=MessagePriority.HIGH,
        )

        data = message.to_dict()
        restored = QueueMessage.from_dict(data)

        assert restored.message_id == message.message_id
        assert restored.payload == message.payload
        assert restored.priority == message.priority


class TestRedisCacheIntegration:
    """Redis缓存集成测试"""

    def test_redis_cache_set_get(self, monkeypatch):
        """Redis缓存应能设置和获取值"""
        mock_client = MagicMock()
        mock_client.get.return_value = "test-value"
        mock_client.set.return_value = True

        cache = RedisCache()
        cache._client = mock_client
        cache._connected = True

        cache.set("test-key", "test-value")
        result = cache.get("test-key")

        assert result == "test-value"

    def test_redis_cache_json(self, monkeypatch):
        """Redis缓存应能处理JSON数据"""
        mock_client = MagicMock()
        mock_client.get.return_value = '{"score": 0.9, "status": "success"}'
        mock_client.set.return_value = True

        cache = RedisCache()
        cache._client = mock_client
        cache._connected = True

        cache.set_json("json-key", {"score": 0.9, "status": "success"})
        result = cache.get_json("json-key")

        assert result == {"score": 0.9, "status": "success"}

    def test_redis_cache_fallback_to_memory(self, monkeypatch):
        """Redis缓存应能在Redis不可用时降级到内存"""
        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("Redis unavailable")
        mock_client.set.side_effect = Exception("Redis unavailable")

        cache = RedisCache()
        cache._client = mock_client
        cache._connected = True

        cache.set("fallback-key", "fallback-value", ex=300)
        result = cache.get("fallback-key")

        assert result == "fallback-value"

    def test_redis_cache_distributed_lock(self, monkeypatch):
        """Redis缓存应能获取分布式锁"""
        mock_client = MagicMock()
        mock_client.set.return_value = True

        cache = RedisCache()
        cache._client = mock_client
        cache._connected = True

        acquired = cache.acquire_lock("cache-lock")
        assert acquired is True

        released = cache.release_lock("cache-lock")
        mock_client.delete.assert_called_once()

    def test_redis_cache_circuit_breaker_state(self, monkeypatch):
        """Redis缓存应能存储熔断器状态"""
        mock_client = MagicMock()
        mock_client.get.return_value = '{"state": "closed", "failure_count": 0}'
        mock_client.set.return_value = True

        cache = RedisCache()
        cache._client = mock_client
        cache._connected = True

        state = {"state": "closed", "failure_count": 0}
        cache.set_circuit_breaker_state("test-breaker", state)
        retrieved = cache.get_circuit_breaker_state("test-breaker")

        assert retrieved is not None


class TestDistributedComponentsCombined:
    """分布式组件组合集成测试"""

    def test_lock_and_rate_limit_combined(self, mock_redis):
        """分布式锁和限流器应能协同工作"""
        lock = DistributedLock(mock_redis, "combined-resource")
        bucket = TokenBucket(mock_redis, "combined-user")

        lock.acquire()
        rate_result = bucket.allow()

        assert lock.is_acquired is True
        assert rate_result.allowed is True

        lock.release()

    def test_cache_and_queue_combined(self, mock_redis):
        """缓存和队列应能协同工作"""
        config = QueueConfig(queue_name="combined-queue")
        queue = RedisListQueue(mock_redis, config)

        message = QueueMessage(
            message_id="combined-001",
            payload={"task": "evaluate", "cache_key": "eval-result-001"},
        )

        async def test_combined():
            await queue.publish(message)
            mock_redis.lpush.assert_called()

        asyncio.run(test_combined())