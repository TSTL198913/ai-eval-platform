"""
分布式核心组件包

包含:
- DistributedLock: 分布式锁
- CircuitBreaker: 熔断器
- RateLimiter: 限流器
- MessageQueue: 消息队列抽象
"""

from .circuit_breaker import CircuitBreaker
from .circuit_breaker import CircuitBreakerConfig
from .circuit_breaker import CircuitBreakerError
from .circuit_breaker import CircuitBreakerRegistry
from .circuit_breaker import CircuitState
from .circuit_breaker import global_registry
from .lock import DistributedLock
from .lock import LockResult
from .lock import LockState
from .lock import RedLock
from .lock import distributed_lock
from .queue import BaseQueue
from .queue import MessagePriority
from .queue import QueueConfig
from .queue import QueueMessage
from .queue import QueueType
from .queue import RedisListQueue
from .queue import create_queue
from .rate_limiter import MultiDimensionRateLimiter
from .rate_limiter import RateLimitConfig
from .rate_limiter import RateLimitResult
from .rate_limiter import RateLimitStrategy
from .rate_limiter import TokenBucket

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
