"""
熔断器实现 - 防止级联失败

当下游服务连续失败超过阈值时，打开熔断器，快速失败。
一段时间后，进入半开状态，允许探测请求尝试恢复。

支持 Redis 持久化，实现多实例间状态共享。
"""

import asyncio
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, TypeVar, Any

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """熔断器状态"""

    CLOSED = "closed"  # 正常，流量通过
    OPEN = "open"  # 熔断，快速失败
    HALF_OPEN = "half_open"  # 半开，允许探测


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""

    failure_threshold: int = 5  # 连续失败次数阈值，触发熔断
    success_threshold: int = 2  # 半开状态下，连续成功次数，关闭熔断
    timeout_seconds: float = 30.0  # 熔断持续时间，之后进入半开
    half_open_max_calls: int = 3  # 半开状态下最大探测调用数


@dataclass
class CircuitBreakerStats:
    """熔断器统计"""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    state_changes: int = 0
    last_state_change_time: float = field(default_factory=time.time)


class CircuitBreakerError(Exception):
    """熔断器打开时抛出的异常"""

    def __init__(self, message: str = "Circuit breaker is open"):
        self.message = message
        super().__init__(self.message)


class CircuitBreaker:
    """
    熔断器实现

    状态转换:
    - CLOSED -> OPEN: 连续失败达到阈值
    - OPEN -> HALF_OPEN: 超时时间到达
    - HALF_OPEN -> CLOSED: 连续成功达到阈值
    - HALF_OPEN -> OPEN: 探测失败

    支持 Redis 持久化，实现多实例间状态共享。

    使用示例:
        @circuit_breaker.call
        async def call_remote_service():
            return await remote_client.request()
    """

    # Redis key 前缀
    REDIS_KEY_PREFIX = "circuit_breaker:"

    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
        redis_client: Any = None,
        persist_ttl: int = 3600,
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float | None = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()
        self.stats = CircuitBreakerStats()
        self._redis_client = redis_client
        self._persist_ttl = persist_ttl
        self._redis_key = f"{self.REDIS_KEY_PREFIX}{name}"

        # 如果提供了 Redis 客户端，尝试从 Redis 恢复状态
        if self._redis_client:
            self._load_state_from_redis()

    @property
    def state(self) -> CircuitState:
        """获取当前状态"""
        if self._state == CircuitState.OPEN:
            # 检查超时是否到达，到达则进入半开
            if (
                self._last_failure_time
                and time.time() - self._last_failure_time >= self.config.timeout_seconds
            ):
                return CircuitState.HALF_OPEN
        return self._state

    @property
    def is_closed(self) -> bool:
        return self.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        return self.state == CircuitState.HALF_OPEN

    def _record_success(self):
        """记录成功调用"""
        self.stats.successful_calls += 1
        self.stats.total_calls += 1
        self._failure_count = 0

        # 使用 state 属性而非 _state，因为 state 包含时间转换逻辑
        if self.state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.config.success_threshold:
                self._transition_to(CircuitState.CLOSED)

    def _record_failure(self):
        """记录失败调用"""
        self.stats.failed_calls += 1
        self.stats.total_calls += 1
        self._failure_count += 1
        self._success_count = 0
        self._last_failure_time = time.time()

        if self._state == CircuitState.CLOSED:
            if self._failure_count >= self.config.failure_threshold:
                self._transition_to(CircuitState.OPEN)
        elif self._state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.OPEN)

    def _transition_to(self, new_state: CircuitState):
        """状态转换"""
        if self._state == new_state:
            return

        logger.warning(
            f"CircuitBreaker [{self.name}] state transition: "
            f"{self._state.value} -> {new_state.value}"
        )
        self._state = new_state
        self.stats.state_changes += 1
        self.stats.last_state_change_time = time.time()

        # 重置计数器
        if new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
            self._success_count = 0
        elif new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._success_count = 0

        # 持久化状态到 Redis
        if self._redis_client:
            self._save_state_to_redis()

    def _save_state_to_redis(self):
        """将熔断器状态保存到 Redis"""
        if not self._redis_client:
            return

        try:
            state_data = {
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "last_failure_time": self._last_failure_time,
                "half_open_calls": self._half_open_calls,
                "stats": {
                    "total_calls": self.stats.total_calls,
                    "successful_calls": self.stats.successful_calls,
                    "failed_calls": self.stats.failed_calls,
                    "rejected_calls": self.stats.rejected_calls,
                    "state_changes": self.stats.state_changes,
                    "last_state_change_time": self.stats.last_state_change_time,
                },
            }
            self._redis_client.set(
                self._redis_key,
                json.dumps(state_data),
                ex=self._persist_ttl,
            )
            logger.debug(f"CircuitBreaker [{self.name}] state saved to Redis")
        except Exception as e:
            logger.error(f"CircuitBreaker [{self.name}] failed to save state to Redis: {e}")

    def _load_state_from_redis(self):
        """从 Redis 加载熔断器状态"""
        if not self._redis_client:
            return

        try:
            data = self._redis_client.get(self._redis_key)
            if data:
                state_data = json.loads(data)
                self._state = CircuitState(state_data["state"])
                self._failure_count = state_data["failure_count"]
                self._success_count = state_data["success_count"]
                self._last_failure_time = state_data["last_failure_time"]
                self._half_open_calls = state_data["half_open_calls"]

                stats_data = state_data["stats"]
                self.stats.total_calls = stats_data["total_calls"]
                self.stats.successful_calls = stats_data["successful_calls"]
                self.stats.failed_calls = stats_data["failed_calls"]
                self.stats.rejected_calls = stats_data["rejected_calls"]
                self.stats.state_changes = stats_data["state_changes"]
                self.stats.last_state_change_time = stats_data["last_state_change_time"]

                logger.info(
                    f"CircuitBreaker [{self.name}] state loaded from Redis: {self._state.value}"
                )
        except Exception as e:
            logger.error(f"CircuitBreaker [{self.name}] failed to load state from Redis: {e}")

    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        通过熔断器执行调用

        Args:
            func: 异步调用函数
            *args, **kwargs: 函数参数

        Returns:
            函数返回值

        Raises:
            CircuitBreakerError: 熔断器打开时
        """
        current_state = self.state

        if current_state == CircuitState.OPEN:
            self.stats.rejected_calls += 1
            raise CircuitBreakerError(f"Circuit breaker [{self.name}] is OPEN, call rejected")

        if current_state == CircuitState.HALF_OPEN:
            async with self._lock:
                if self._half_open_calls >= self.config.half_open_max_calls:
                    self.stats.rejected_calls += 1
                    raise CircuitBreakerError(
                        f"Circuit breaker [{self.name}] HALF_OPEN max calls reached"
                    )
                self._half_open_calls += 1

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            self._record_success()
            return result
        except Exception:
            self._record_failure()
            raise

    def reset(self):
        """手动重置熔断器"""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        self._half_open_calls = 0
        logger.info(f"CircuitBreaker [{self.name}] has been reset")

        # 重置后保存状态到 Redis
        if self._redis_client:
            self._save_state_to_redis()

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "name": self.name,
            "state": self.state.value,
            "total_calls": self.stats.total_calls,
            "successful_calls": self.stats.successful_calls,
            "failed_calls": self.stats.failed_calls,
            "rejected_calls": self.stats.rejected_calls,
            "state_changes": self.stats.state_changes,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
        }


def circuit_breaker(name: str, config: CircuitBreakerConfig | None = None):
    """
    熔断器装饰器工厂

    使用示例:
        @circuit_breaker("external_api")
        async def call_external_api():
            return await client.request()
    """
    _breaker = CircuitBreaker(name, config)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        async def wrapper(*args, **kwargs) -> T:
            return await _breaker.call(func, *args, **kwargs)

        return wrapper

    return decorator


class CircuitBreakerRegistry:
    """
    熔断器注册中心

    管理多个熔断器，方便统一监控和配置
    """

    _instance: Optional["CircuitBreakerRegistry"] = None

    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> "CircuitBreakerRegistry":
        """获取单例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_or_create(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
    ) -> CircuitBreaker:
        """获取或创建熔断器"""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name, config)
        return self._breakers[name]

    def get(self, name: str) -> CircuitBreaker | None:
        """获取熔断器"""
        return self._breakers.get(name)

    def list_breakers(self) -> dict[str, CircuitBreaker]:
        """列出所有熔断器"""
        return dict(self._breakers)

    def all_stats(self) -> dict:
        """获取所有熔断器统计"""
        return {name: cb.get_stats() for name, cb in self._breakers.items()}


# 全局注册中心 (兼容旧代码)
global_registry = CircuitBreakerRegistry()
