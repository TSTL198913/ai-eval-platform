"""
请求幂等性保障模块

使用 Redis 存储请求 ID，防止重复处理同一请求。
支持多种幂等性策略：
1. 请求 ID 幂等性：基于唯一请求 ID
2. 业务键幂等性：基于业务唯一键（如 case_id + timestamp）
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class IdempotencyStrategy(Enum):
    """幂等性策略"""

    REQUEST_ID = "request_id"  # 基于请求 ID
    BUSINESS_KEY = "business_key"  # 基于业务键
    COMPOSITE = "composite"  # 组合策略


@dataclass
class IdempotencyConfig:
    """幂等性配置"""

    ttl_seconds: int = 3600  # 幂等性记录 TTL（1小时）
    key_prefix: str = "idempotency:"  # Redis key 前缀
    strategy: IdempotencyStrategy = IdempotencyStrategy.REQUEST_ID


class IdempotencyError(Exception):
    """幂等性检查失败异常"""

    def __init__(self, message: str = "Duplicate request detected"):
        self.message = message
        super().__init__(self.message)


class IdempotencyChecker:
    """
    幂等性检查器

    使用 Redis 存储已处理的请求 ID，防止重复处理。

    使用示例:
        checker = IdempotencyChecker(redis_client)

        # 检查并处理
        if checker.check(request_id):
            result = process_request()
            checker.mark_processed(request_id, result)
        else:
            result = checker.get_cached_result(request_id)
    """

    def __init__(
        self,
        redis_client: Any,
        config: IdempotencyConfig | None = None,
    ):
        self._redis = redis_client
        self._config = config or IdempotencyConfig()

    def _generate_key(self, request_id: str) -> str:
        """生成 Redis key"""
        return f"{self._config.key_prefix}{request_id}"

    def _generate_business_key(self, *args, **kwargs) -> str:
        """生成业务键"""
        key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]

    def check(self, request_id: str) -> bool:
        """
        检查请求是否已处理

        Args:
            request_id: 请求唯一标识

        Returns:
            True: 请求未处理，可以继续
            False: 请求已处理，应使用缓存结果
        """
        key = self._generate_key(request_id)
        exists = self._redis.exists(key)
        return not exists

    def mark_processing(self, request_id: str) -> bool:
        """
        标记请求正在处理

        Args:
            request_id: 请求唯一标识

        Returns:
            True: 成功标记
            False: 已被其他实例标记
        """
        key = self._generate_key(request_id)
        # 使用 SETNX 实现原子性检查
        result = self._redis.setnx(key, json.dumps({"status": "processing", "timestamp": time.time()}))
        if result:
            self._redis.expire(key, self._config.ttl_seconds)
        return result

    def mark_processed(
        self,
        request_id: str,
        result: Any = None,
        metadata: dict | None = None,
    ) -> bool:
        """
        标记请求已处理，并缓存结果

        Args:
            request_id: 请求唯一标识
            result: 处理结果（可选）
            metadata: 元数据（可选）

        Returns:
            True: 成功标记
        """
        key = self._generate_key(request_id)
        data = {
            "status": "processed",
            "timestamp": time.time(),
            "result": result,
            "metadata": metadata or {},
        }
        self._redis.set(key, json.dumps(data), ex=self._config.ttl_seconds)
        logger.debug(f"Request {request_id} marked as processed")
        return True

    def get_cached_result(self, request_id: str) -> Any | None:
        """
        获取缓存的处理结果

        Args:
            request_id: 请求唯一标识

        Returns:
            缓存的结果，如果不存在返回 None
        """
        key = self._generate_key(request_id)
        data = self._redis.get(key)
        if data:
            parsed = json.loads(data)
            if parsed.get("status") == "processed":
                return parsed.get("result")
        return None

    def get_status(self, request_id: str) -> dict | None:
        """
        获取请求状态

        Args:
            request_id: 请求唯一标识

        Returns:
            状态信息字典
        """
        key = self._generate_key(request_id)
        data = self._redis.get(key)
        if data:
            return json.loads(data)
        return None

    def clear(self, request_id: str) -> bool:
        """
        清除幂等性记录

        Args:
            request_id: 请求唯一标识

        Returns:
            True: 成功清除
        """
        key = self._generate_key(request_id)
        self._redis.delete(key)
        logger.debug(f"Idempotency record for {request_id} cleared")
        return True


def idempotent(
    redis_client: Any,
    key_extractor: Callable[..., str] | None = None,
    config: IdempotencyConfig | None = None,
):
    """
    幂等性装饰器

    使用示例:
        @idempotent(redis_client, key_extractor=lambda req: req.id)
        async def process_request(request):
            return await do_something(request)
    """
    checker = IdempotencyChecker(redis_client, config)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        async def wrapper(*args, **kwargs) -> T:
            # 提取请求 ID
            if key_extractor:
                request_id = key_extractor(*args, **kwargs)
            else:
                # 默认使用第一个参数作为请求 ID
                request_id = str(args[0]) if args else str(kwargs.get("id", ""))

            # 检查幂等性
            if not checker.check(request_id):
                cached = checker.get_cached_result(request_id)
                if cached is not None:
                    logger.info(f"Returning cached result for request {request_id}")
                    return cached
                raise IdempotencyError(f"Request {request_id} is already being processed")

            # 标记正在处理
            if not checker.mark_processing(request_id):
                raise IdempotencyError(f"Request {request_id} is already being processed by another instance")

            # 执行函数
            try:
                result = await func(*args, **kwargs)
                checker.mark_processed(request_id, result)
                return result
            except Exception as e:
                # 失败时清除标记，允许重试
                checker.clear(request_id)
                raise

        return wrapper

    return decorator