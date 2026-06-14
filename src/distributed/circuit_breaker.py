"""
熔断器实现 - 防止级联失败

当下游服务连续失败超过阈值时，打开熔断器，快速失败。
一段时间后，进入半开状态，允许探测请求尝试恢复。
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional, TypeVar

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
    failure_threshold: int = 5          # 连续失败次数阈值，触发熔断
    success_threshold: int = 2          # 半开状态下，连续成功次数，关闭熔断
    timeout_seconds: float = 30.0        # 熔断持续时间，之后进入半开
    half_open_max_calls: int = 3        # 半开状态下最大探测调用数


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

    使用示例:
        @circuit_breaker.call
        async def call_remote_service():
            return await remote_client.request()
    """

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()
        self.stats = CircuitBreakerStats()

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
            raise CircuitBreakerError(
                f"Circuit breaker [{self.name}] is OPEN, call rejected"
            )

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


def circuit_breaker(name: str, config: Optional[CircuitBreakerConfig] = None):
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
        config: Optional[CircuitBreakerConfig] = None,
    ) -> CircuitBreaker:
        """获取或创建熔断器"""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name, config)
        return self._breakers[name]

    def get(self, name: str) -> Optional[CircuitBreaker]:
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
