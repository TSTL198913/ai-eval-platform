"""
熔断器实现 - 防止级联失败

当下游服务连续失败超过阈值时，打开熔断器，快速失败。
一段时间后，进入半开状态，允许探测请求尝试恢复。

支持 Redis 持久化，实现多实例间状态共享。
"""

import asyncio
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, TypeVar

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
        auto_load_redis: bool = True,
        sync_interval: float = 5.0,
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float | None = None
        self._half_open_calls = 0
        self._sync_lock = threading.RLock()
        self.stats = CircuitBreakerStats()
        self._redis_client = redis_client
        self._persist_ttl = persist_ttl
        self._redis_key = f"{self.REDIS_KEY_PREFIX}{name}"
        self._redis_lock_key = f"{self.REDIS_KEY_PREFIX}{name}:lock"
        self._sync_interval = sync_interval
        self._last_sync_time: float = 0.0

        if self._redis_client and auto_load_redis:
            self._load_state_from_redis()

    @property
    def state(self) -> CircuitState:
        """获取当前状态（线程安全，自动检查超时转换和 Redis 同步）"""
        self._sync_state_from_redis()
        self._check_timeout_transition()
        with self._sync_lock:
            return self._state

    def _check_timeout_transition(self) -> CircuitState:
        """检查超时并触发状态转换（仅在需要时调用）"""
        with self._sync_lock:
            if self._state == CircuitState.OPEN:
                if (
                    self._last_failure_time
                    and time.time() - self._last_failure_time >= self.config.timeout_seconds
                ):
                    self._transition_to(CircuitState.HALF_OPEN)
                    return CircuitState.HALF_OPEN
            return self._state

    def _sync_state_from_redis(self):
        """定期从 Redis 同步状态（心跳同步机制）"""
        if not self._redis_client:
            return

        try:
            if not self._redis_client.is_connected:
                return
        except Exception:
            return

        now = time.time()
        if now - self._last_sync_time < self._sync_interval:
            return

        self._last_sync_time = now
        try:
            state_data = self._redis_client.get_circuit_breaker_state(self.name)
            if state_data:
                with self._sync_lock:
                    remote_state = CircuitState(state_data["state"])
                    if remote_state != self._state:
                        logger.info(
                            f"CircuitBreaker [{self.name}] sync state from Redis: "
                            f"{self._state.value} -> {remote_state.value}"
                        )
                        self._state = remote_state
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
        except Exception as e:
            logger.debug(f"CircuitBreaker [{self.name}] failed to sync state from Redis: {e}")

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
        """记录成功调用（带 Redis 原子计数）"""
        with self._sync_lock:
            self.stats.successful_calls += 1
            self.stats.total_calls += 1

            if self._redis_client:
                self._redis_client.increment_success_count(self.name)
                self._redis_client.reset_counts(self.name)

            self._failure_count = 0

            if self.state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._transition_to(CircuitState.CLOSED)

    def _record_failure(self):
        """记录失败调用（带 Redis 原子计数）"""
        with self._sync_lock:
            self.stats.failed_calls += 1
            self.stats.total_calls += 1
            self._failure_count += 1
            self._success_count = 0
            self._last_failure_time = time.time()

            if self._redis_client:
                redis_failure_count = self._redis_client.increment_failure_count(self.name)
                if redis_failure_count and isinstance(redis_failure_count, int):
                    self._failure_count = max(self._failure_count, redis_failure_count)

            if self._state == CircuitState.CLOSED:
                if self._failure_count >= self.config.failure_threshold:
                    self._transition_to(CircuitState.OPEN)
            elif self._state == CircuitState.HALF_OPEN:
                self._transition_to(CircuitState.OPEN)

    def _transition_to(self, new_state: CircuitState):
        """状态转换（带分布式锁）"""
        if self._state == new_state:
            return

        acquired = False
        try:
            if self._redis_client:
                acquired = self._redis_client.acquire_lock(self._redis_lock_key, timeout=5)
                if not acquired:
                    logger.warning(
                        f"CircuitBreaker [{self.name}] failed to acquire lock, "
                        f"state transition aborted: {self._state.value} -> {new_state.value}"
                    )
                    return
            else:
                acquired = True

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
        finally:
            if acquired and self._redis_client:
                self._redis_client.release_lock(self._redis_lock_key)

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
            self._redis_client.set_circuit_breaker_state(
                self.name,
                state_data,
                ttl=self._persist_ttl,
            )
            logger.debug(f"CircuitBreaker [{self.name}] state saved to Redis")
        except Exception as e:
            logger.error(f"CircuitBreaker [{self.name}] failed to save state to Redis: {e}")

    def _load_state_from_redis(self):
        """从 Redis 加载熔断器状态"""
        if not self._redis_client:
            return

        try:
            import json

            state_data = self._redis_client.get_circuit_breaker_state(self.name)
            if state_data:
                if isinstance(state_data, str):
                    state_data = json.loads(state_data)
                with self._sync_lock:
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

                self._last_sync_time = time.time()
                logger.info(
                    f"CircuitBreaker [{self.name}] state loaded from Redis: {self._state.value}"
                )
        except Exception as e:
            logger.error(f"CircuitBreaker [{self.name}] failed to load state from Redis: {e}")

    def call_sync(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        通过熔断器执行同步调用

        Args:
            func: 同步调用函数
            *args, **kwargs: 函数参数

        Returns:
            函数返回值

        Raises:
            CircuitBreakerError: 熔断器打开时
        """
        # 修复：在调用前主动检查超时转换，而非每次读取属性时检查
        current_state = self._check_timeout_transition()

        if current_state == CircuitState.OPEN:
            self.stats.rejected_calls += 1
            raise CircuitBreakerError(f"Circuit breaker [{self.name}] is OPEN, call rejected")

        if current_state == CircuitState.HALF_OPEN:
            with self._sync_lock:
                if self._half_open_calls >= self.config.half_open_max_calls:
                    self.stats.rejected_calls += 1
                    raise CircuitBreakerError(
                        f"Circuit breaker [{self.name}] HALF_OPEN max calls reached"
                    )
                self._half_open_calls += 1

        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except Exception:
            self._record_failure()
            raise

    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        通过熔断器执行异步调用

        Args:
            func: 异步调用函数
            *args, **kwargs: 函数参数

        Returns:
            函数返回值

        Raises:
            CircuitBreakerError: 熔断器打开时
        """
        def _acquire_half_open_permit():
            with self._sync_lock:
                if self._half_open_calls >= self.config.half_open_max_calls:
                    return False
                self._half_open_calls += 1
            return True

        current_state = self.state

        if current_state == CircuitState.OPEN:
            self.stats.rejected_calls += 1
            raise CircuitBreakerError(f"Circuit breaker [{self.name}] is OPEN, call rejected")

        if current_state == CircuitState.HALF_OPEN:
            acquired = await asyncio.to_thread(_acquire_half_open_permit)
            if not acquired:
                self.stats.rejected_calls += 1
                raise CircuitBreakerError(
                    f"Circuit breaker [{self.name}] HALF_OPEN max calls reached"
                )

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
        """手动重置熔断器（线程安全）"""
        with self._sync_lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None
            self._half_open_calls = 0
            logger.info(f"CircuitBreaker [{self.name}] has been reset")

            # 重置后保存状态到 Redis
            if self._redis_client:
                self._redis_client.delete_circuit_breaker_state(self.name)

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
    熔断器装饰器工厂（支持同步和异步函数）

    使用示例:
        @circuit_breaker("external_api")
        async def call_external_api():
            return await client.request()

        @circuit_breaker("sync_api")
        def call_sync_api():
            return client.request()
    """
    _breaker = CircuitBreaker(name, config)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        if asyncio.iscoroutinefunction(func):

            async def async_wrapper(*args, **kwargs) -> T:
                return await _breaker.call(func, *args, **kwargs)

            return async_wrapper
        else:

            def sync_wrapper(*args, **kwargs) -> T:
                return _breaker.call_sync(func, *args, **kwargs)

            return sync_wrapper

    return decorator


class CircuitBreakerRegistry:
    """
    熔断器注册中心

    管理多个熔断器，方便统一监控和配置
    支持 Redis 持久化，实现多实例间状态共享
    """

    _instance: Optional["CircuitBreakerRegistry"] = None
    _instance_lock = threading.Lock()

    def __init__(self, redis_client: Any = None):
        self._breakers: dict[str, CircuitBreaker] = {}
        self._redis_client = redis_client

    @classmethod
    def get_instance(cls) -> "CircuitBreakerRegistry":
        """获取单例（线程安全双重检查锁定）"""
        if cls._instance is None:
            with cls._instance_lock:
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
            self._breakers[name] = CircuitBreaker(name, config, redis_client=self._redis_client)
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

    def health_check(self) -> dict:
        """健康检查"""
        result = {"redis_connected": self._redis_client.is_connected}
        for name, cb in self._breakers.items():
            result[name] = {
                "state": cb.state.value,
                "is_open": cb.is_open,
            }
        return result


# 全局注册中心 (兼容旧代码)
# 使用完全延迟初始化，仅在首次访问时创建
_global_registry: Optional["CircuitBreakerRegistry"] = None


def get_global_registry() -> CircuitBreakerRegistry:
    """获取全局熔断器注册中心（延迟初始化）"""
    global _global_registry
    if _global_registry is None:
        try:
            from .redis_cache import redis_cache

            _global_registry = CircuitBreakerRegistry(redis_client=redis_cache)
        except Exception:
            _global_registry = CircuitBreakerRegistry()
    return _global_registry


# 兼容旧代码 - 使用代理对象实现完全延迟初始化
class _GlobalRegistryProxy:
    """全局注册中心代理，实现完全延迟初始化"""

    def __getattr__(self, name):
        return getattr(get_global_registry(), name)


global_registry = _GlobalRegistryProxy()
