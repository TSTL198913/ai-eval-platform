"""
统一缓存装饰器

支持同步和异步函数，统一两个独立实现：
- 同步版本：使用全局 EvaluationCache（基于 functools.lru_cache 风格）
- 异步版本：支持 LRUCache + TTL + 自定义 key_generator

使用示例:
    # 同步函数（自动使用全局缓存）
    @cached(key_prefix="user")
    def get_user(user_id: int):
        return db.query(user_id)

    # 异步函数（自定义缓存和 TTL）
    cache = LRUCache(max_size=1000)
    @cached(cache=cache, ttl=60.0, key_generator=lambda x: f"eval:{x}")
    async def evaluate(x):
        return await llm_call(x)
"""

import asyncio
import hashlib
import json
from functools import wraps
from typing import Any, Callable, TypeVar, Union

from src.infra.cache import EvaluationCache
from src.infra.performance import LRUCache
from src.infra.logger import logger

T = TypeVar("T")

# 全局默认同步缓存实例
_default_sync_cache = EvaluationCache(max_size=512)


def _generate_default_key(prefix: str, func_name: str, args: tuple, kwargs: dict) -> str:
    """生成默认缓存键"""
    try:
        key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    except (TypeError, ValueError):
        key_data = str(args) + str(sorted(kwargs.items()))

    hash_suffix = hashlib.md5(key_data.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{func_name}:{hash_suffix}" if prefix else f"{func_name}:{hash_suffix}"


def cached(
    cache: Union[EvaluationCache, LRUCache, None] = None,
    *,
    key_prefix: str = "",
    key_generator: Callable[..., str] | None = None,
    ttl: float | None = None,
):
    """
    统一缓存装饰器

    Args:
        cache: 缓存实例（EvaluationCache 或 LRUCache），None 时使用全局默认缓存
        key_prefix: 同步模式下的 key 前缀（向后兼容）
        key_generator: 自定义键生成函数
        ttl: 过期时间（秒），仅 LRUCache 支持

    使用示例:
        # 方式1: 同步函数，使用全局缓存
        @cached()
        def expensive_sync_fn(x):
            return compute(x)

        # 方式2: 同步函数，指定 key 前缀
        @cached(key_prefix="user")
        def get_user(user_id):
            return db.query(user_id)

        # 方式3: 异步函数，指定缓存和 TTL
        cache = LRUCache(max_size=1000)
        @cached(cache=cache, ttl=60.0)
        async def expensive_async_fn(x):
            return await llm_call(x)

        # 方式4: 自定义键生成
        @cached(cache=cache, key_generator=lambda x: f"result:{x}")
        async def compute(x):
            return expensive(x)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        # 确定使用的缓存实例
        if cache is not None:
            target_cache = cache
        else:
            target_cache = _default_sync_cache

        is_lru = isinstance(target_cache, LRUCache)
        is_eval = isinstance(target_cache, EvaluationCache)

        if is_lru:
            # 异步模式（LRUCache 支持异步操作）
            @wraps(func)
            async def async_wrapper(*args, **kwargs) -> T:
                if key_generator:
                    key = key_generator(*args, **kwargs)
                else:
                    key = _generate_default_key(key_prefix, func.__name__, args, kwargs)

                cached_value = await target_cache.get(key)
                if cached_value is not None:
                    logger.debug(f"Cache hit for key: {key}")
                    return cached_value

                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                await target_cache.set(key, result, ttl)
                logger.debug(f"Cache set for key: {key}")
                return result

            return async_wrapper

        elif is_eval:
            # 同步模式（EvaluationCache 是同步的）
            @wraps(func)
            def sync_wrapper(*args, **kwargs) -> T:
                if key_generator:
                    key = key_generator(*args, **kwargs)
                else:
                    key = _generate_default_key(key_prefix, func.__name__, args, kwargs)

                cached_result = target_cache.get(key)
                if cached_result is not None:
                    logger.debug(f"Cache hit for key: {key}")
                    return cached_result

                result = func(*args, **kwargs)
                target_cache.set(key, result)
                logger.debug(f"Cache set for key: {key}")
                return result

            return sync_wrapper

        else:
            raise TypeError(
                f"Unsupported cache type: {type(cache).__name__}. "
                f"Expected EvaluationCache or LRUCache."
            )

    return decorator


# 便捷别名（向后兼容）
sync_cached = cached  # 同步版本别名
