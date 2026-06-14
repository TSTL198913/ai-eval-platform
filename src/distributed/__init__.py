"""
分布式核心组件包

包含:
- DistributedLock: 分布式锁
- CircuitBreaker: 熔断器
- RateLimiter: 限流器
- MessageQueue: 消息队列抽象
"""

from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerRegistry,
    CircuitState,
    global_registry,
)
from .lock import DistributedLock, LockResult, LockState, RedLock, distributed_lock
from .queue import (
    BaseQueue,
    MessagePriority,
    QueueConfig,
    QueueMessage,
    QueueType,
    RedisListQueue,
    create_queue,
)
from .rate_limiter import (
    MultiDimensionRateLimiter,
    RateLimitConfig,
    RateLimitResult,
    RateLimitStrategy,
    TokenBucket,
)

__all__ = [
    # Lock
    "DistributedLock",
    "LockResult",
    "LockState",
    "RedLock",
    "distributed_lock",
    # Circuit Breaker
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerError",
    "CircuitBreakerRegistry",
    "CircuitState",
    "global_registry",
    # Rate Limiter
    "MultiDimensionRateLimiter",
    "RateLimitConfig",
    "RateLimitResult",
    "RateLimitStrategy",
    "TokenBucket",
    # Queue
    "BaseQueue",
    "MessagePriority",
    "QueueConfig",
    "QueueMessage",
    "QueueType",
    "RedisListQueue",
    "create_queue",
]
