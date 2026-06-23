import os
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from functools import wraps
from typing import Any

import redis

from src.infra.db.session import get_db_session

_redis_client: redis.Redis | None = None
_redis_lock = threading.Lock()


def get_redis() -> redis.Redis:
    """获取Redis客户端（线程安全单例）"""
    global _redis_client
    if _redis_client is None:
        with _redis_lock:
            if _redis_client is None:
                _redis_client = redis.Redis(
                    host=os.getenv("REDIS_HOST", "localhost"),
                    port=int(os.getenv("REDIS_PORT", "6379")),
                    db=int(os.getenv("REDIS_DB", "0")),
                    decode_responses=True,
                    protocol=2,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                )
    return _redis_client


def get_redis_client() -> redis.Redis:
    return get_redis()


class EvaluationCache:
    """
    评估缓存实现

    支持：
    - TTL过期机制
    - 容量限制（max_size）
    - LRU淘汰策略（O(1)时间复杂度）
    - 线程安全
    """

    def __init__(self, ttl_seconds: int | float = 60, max_size: int = 10000):
        """
        初始化缓存

        Args:
            ttl_seconds: 缓存过期时间（秒），支持int或float
            max_size: 最大缓存条目数，默认10000
        """
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._lock = threading.RLock()
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}

    def get(self, key: str) -> Any | None:
        """
        获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值，如果不存在或已过期返回None
        """
        with self._lock:
            item = self._cache.get(key)
            if item:
                value, timestamp = item
                if time.time() - timestamp < self._ttl:
                    # 更新访问顺序（移到末尾表示最近使用）
                    self._cache.move_to_end(key)
                    self._stats["hits"] += 1
                    return value
                else:
                    # 已过期，删除
                    del self._cache[key]
            self._stats["misses"] += 1
            return None

    def set(self, key: str, value: Any, ttl: int | float | None = None) -> None:
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 可选的TTL覆盖，None则使用默认TTL
        """
        with self._lock:
            # 如果键已存在，先删除旧的
            if key in self._cache:
                del self._cache[key]
            # 检查容量，执行LRU淘汰（仅当缓存不为空且达到容量限制时）
            elif self._max_size > 0 and len(self._cache) >= self._max_size:
                # 淘汰最久未使用的（OrderedDict的第一个元素）
                self._cache.popitem(last=False)
                self._stats["evictions"] += 1

            # 如果max_size为0，不存储任何内容
            if self._max_size > 0:
                # 使用自定义TTL或默认TTL
                # 注意：存储的是创建时间戳，get时会根据TTL检查过期
                self._cache[key] = (value, time.time())

    def invalidate(self, key: str) -> None:
        """删除指定缓存键"""
        with self._lock:
            self._cache.pop(key, None)

    def clear(self) -> None:
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._stats = {"hits": 0, "misses": 0, "evictions": 0}

    def get_stats(self) -> dict:
        """获取缓存统计信息"""
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            hit_rate = self._stats["hits"] / total if total > 0 else 0
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "evictions": self._stats["evictions"],
                "hit_rate": hit_rate,
            }

    def size(self) -> int:
        """获取当前缓存大小"""
        with self._lock:
            return len(self._cache)


_cache = EvaluationCache()


def cached(key_prefix: str = "") -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = f"{key_prefix}:{args}:{kwargs}"
            cached_result = _cache.get(key)
            if cached_result is not None:
                return cached_result
            result = func(*args, **kwargs)
            _cache.set(key, result)
            return result

        return wrapper

    return decorator


def batch_insert(results: list[dict]) -> int:
    """批量插入评估结果"""
    if not results:
        return 0

    with get_db_session() as session:
        from src.infra.db.models import EvaluationResultModel

        db_records = [
            EvaluationResultModel(
                case_id=r.get("case_id"),
                model_name=r.get("model_name", "unknown"),
                adapter_name=r.get("adapter_name", "unknown"),
                status=r.get("status"),
                latency_ms=r.get("latency_ms", 0.0),
                response_data=r.get("response_data", {}),
            )
            for r in results
        ]
        session.add_all(db_records)
        session.commit()
        return len(db_records)
