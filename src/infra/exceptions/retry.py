"""
重试和降级策略模块

提供灵活的重试机制和优雅降级策略，增强系统稳定性。
"""

import functools
import logging
import threading
import time
from collections.abc import Callable
from typing import Any

from tenacity import (
    after_log,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_attempts: int = 3,
    wait_min: float = 1.0,
    wait_max: float = 10.0,
    exception_types: tuple[type[Exception], ...] = (Exception,),
    logger_name: str = __name__,
):
    """
    装饰器：添加指数退避重试机制

    Args:
        max_attempts: 最大重试次数
        wait_min: 最小等待时间（秒）
        wait_max: 最大等待时间（秒）
        exception_types: 需要重试的异常类型
        logger_name: 日志记录器名称
    """
    log = logging.getLogger(logger_name)

    def decorator(func: Callable) -> Callable:
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=wait_min, max=wait_max),
            retry=retry_if_exception_type(exception_types),
            before_sleep=before_sleep_log(log, logging.WARNING),
            after=after_log(log, logging.INFO),
        )
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            return func(*args, **kwargs)

        return wrapper

    return decorator


class CircuitBreaker:
    """
    熔断器模式实现

    当服务失败率超过阈值时，自动熔断，防止级联故障。
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_requests: int = 3,
    ):
        """
        Args:
            failure_threshold: 失败阈值，超过此值触发熔断
            recovery_timeout: 熔断恢复时间（秒）
            half_open_max_requests: 半开状态下允许的最大请求数
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_requests = half_open_max_requests

        self._lock = threading.Lock()
        self._state = "closed"  # closed, open, half_open
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._half_open_request_count = 0

    def __call__(self, func: Callable) -> Callable:
        """作为装饰器使用"""

        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            return self.execute(func, *args, **kwargs)

        return wrapper

    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """执行函数，应用熔断逻辑"""
        current_time = time.time()

        # 检查熔断状态（加锁）
        with self._lock:
            if self._state == "open":
                # 检查是否可以尝试恢复
                if current_time - self._last_failure_time >= self.recovery_timeout:
                    self._state = "half_open"
                    self._half_open_request_count = 0
                    logger.info("熔断器从 OPEN 状态转换为 HALF_OPEN 状态")
                else:
                    raise CircuitBreakerError("服务已熔断，请稍后重试")

            if self._state == "half_open":
                # 限制半开状态下的请求数
                if self._half_open_request_count >= self.half_open_max_requests:
                    raise CircuitBreakerError("熔断器半开状态请求数已达上限")
                self._half_open_request_count += 1

        try:
            result = func(*args, **kwargs)
            # 成功，重置计数器（加锁）
            with self._lock:
                self._failure_count = 0
                if self._state == "half_open":
                    self._state = "closed"
                    logger.info("熔断器从 HALF_OPEN 状态转换为 CLOSED 状态")
            return result
        except Exception:
            # 失败，增加计数器（加锁）
            with self._lock:
                self._failure_count += 1
                self._last_failure_time = current_time

                if self._state == "closed" and self._failure_count >= self.failure_threshold:
                    self._state = "open"
                    logger.error(f"熔断器触发！连续失败 {self.failure_threshold} 次")

            raise

    @property
    def state(self) -> str:
        """获取当前状态"""
        return self._state


class CircuitBreakerError(Exception):
    """熔断器错误"""

    pass


def fallback_to(default_value: Any = None, exception_types: tuple = (Exception,)):
    """
    装饰器：优雅降级，当函数失败时返回默认值

    Args:
        default_value: 降级时返回的默认值
        exception_types: 需要降级处理的异常类型
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except exception_types:
                logger.warning(f"降级触发: {func.__name__} 失败，返回默认值: {default_value}")
                return default_value

        return wrapper

    return decorator
