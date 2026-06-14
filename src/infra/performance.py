"""
性能优化模块

包含：
1. 智能缓存管理
2. 连接池优化
3. 异步批处理
4. 结果预计算
"""

import asyncio
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class CacheConfig:
    """缓存配置"""

    max_size: int = 1000  # 最大缓存条目数
    ttl_seconds: float = 300.0  # 默认 TTL（5分钟）
    eviction_policy: str = "lru"  # 淘汰策略：lru, lfu, fifo


@dataclass
class CacheEntry:
    """缓存条目"""

    value: Any
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0
    hits: int = 0
    key: str = ""

    def __post_init__(self):
        if self.expires_at == 0:
            self.expires_at = self.created_at + 300.0

    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def increment_hit(self):
        self.hits += 1


class LRUCache:
    """
    LRU 缓存实现

    使用最近最少使用策略管理缓存条目。
    """

    def __init__(self, config: CacheConfig | None = None):
        self._config = config or CacheConfig()
        self._cache: dict[str, CacheEntry] = {}
        self._access_order: list[str] = []
        self._lock = asyncio.Lock()
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}

    async def get(self, key: str) -> Any | None:
        """获取缓存值"""
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None or entry.is_expired():
                self._stats["misses"] += 1
                return None

            entry.increment_hit()
            self._stats["hits"] += 1

            # 更新访问顺序（LRU）
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)

            return entry.value

    async def set(self, key: str, value: Any, ttl: float | None = None) -> bool:
        """设置缓存值"""
        async with self._lock:
            # 如果已存在，先移除
            if key in self._cache:
                if key in self._access_order:
                    self._access_order.remove(key)

            # 检查容量，必要时淘汰
            while len(self._cache) >= self._config.max_size:
                self._evict()

            # 创建新条目
            expires_at = time.time() + (ttl or self._config.ttl_seconds)
            entry = CacheEntry(value=value, key=key, expires_at=expires_at)
            self._cache[key] = entry
            self._access_order.append(key)

            return True

    def _evict(self):
        """淘汰最久未使用的条目"""
        if not self._access_order:
            return

        oldest_key = self._access_order.pop(0)
        if oldest_key in self._cache:
            del self._cache[oldest_key]
            self._stats["evictions"] += 1
            logger.debug(f"Evicted cache entry: {oldest_key}")

    async def delete(self, key: str) -> bool:
        """删除缓存条目"""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
                return True
            return False

    async def clear(self):
        """清空缓存"""
        async with self._lock:
            self._cache.clear()
            self._access_order.clear()

    def get_stats(self) -> dict:
        """获取缓存统计"""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total > 0 else 0
        return {
            "size": len(self._cache),
            "max_size": self._config.max_size,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "evictions": self._stats["evictions"],
            "hit_rate": hit_rate,
        }


def cached(
    cache: LRUCache,
    key_generator: Callable[..., str] | None = None,
    ttl: float | None = None,
):
    """
    缓存装饰器

    使用示例:
        cache = LRUCache()

        @cached(cache, key_generator=lambda x: f"result:{x}")
        async def compute(x):
            return expensive_computation(x)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # 生成缓存键
            if key_generator:
                key = key_generator(*args, **kwargs)
            else:
                key = f"{func.__name__}:{json.dumps(args)}:{json.dumps(kwargs)}"

            # 尝试从缓存获取
            cached_value = await cache.get(key)
            if cached_value is not None:
                logger.debug(f"Cache hit for key: {key}")
                return cached_value

            # 执行函数
            result = await func(*args, **kwargs)

            # 存入缓存
            await cache.set(key, result, ttl)
            logger.debug(f"Cache set for key: {key}")

            return result

        return wrapper

    return decorator


class BatchProcessor:
    """
    批处理器

    将多个请求合并为批量处理，减少 I/O 操作次数。
    """

    def __init__(
        self,
        batch_size: int = 100,
        batch_timeout: float = 0.1,  # 100ms
    ):
        self._batch_size = batch_size
        self._batch_timeout = batch_timeout
        self._pending: list[tuple[Any, asyncio.Future]] = []
        self._lock = asyncio.Lock()
        self._processor_task: asyncio.Task | None = None

    async def add(self, item: Any) -> Any:
        """添加待处理项"""
        future = asyncio.Future()

        async with self._lock:
            self._pending.append((item, future))

            # 达到批量大小，立即处理
            if len(self._pending) >= self._batch_size:
                await self._process_batch()

        return await future

    async def _process_batch(self):
        """处理批量请求"""
        if not self._pending:
            return

        batch = self._pending.copy()
        self._pending.clear()

        # 执行批量处理
        try:
            results = await self._execute_batch([item for item, _ in batch])
            for (_, future), result in zip(batch, results, strict=False):
                future.set_result(result)
        except Exception as e:
            for _, future in batch:
                future.set_exception(e)

    async def _execute_batch(self, items: list[Any]) -> list[Any]:
        """执行批量操作（需子类实现）"""
        return items

    async def start(self):
        """启动批处理器"""
        self._processor_task = asyncio.create_task(self._run_periodically())

    async def stop(self):
        """停止批处理器"""
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass

    async def _run_periodically(self):
        """定期处理待处理项"""
        while True:
            await asyncio.sleep(self._batch_timeout)
            async with self._lock:
                if self._pending:
                    await self._process_batch()


class ConnectionPoolMonitor:
    """
    连接池监控器

    监控和优化数据库、Redis 连接池使用。
    """

    def __init__(self):
        self._metrics: dict[str, dict] = {}

    def register_pool(self, name: str, pool: Any):
        """注册连接池"""
        self._metrics[name] = {
            "pool": pool,
            "total_connections": 0,
            "active_connections": 0,
            "idle_connections": 0,
            "wait_count": 0,
            "wait_time_ms": 0,
        }

    def update_metrics(self, name: str, metrics: dict):
        """更新连接池指标"""
        if name in self._metrics:
            self._metrics[name].update(metrics)

    def get_pool_stats(self, name: str) -> dict | None:
        """获取连接池统计"""
        return self._metrics.get(name)

    def get_all_stats(self) -> dict:
        """获取所有连接池统计"""
        return {
            name: {
                "total": data.get("total_connections", 0),
                "active": data.get("active_connections", 0),
                "idle": data.get("idle_connections", 0),
                "wait_count": data.get("wait_count", 0),
                "wait_time_ms": data.get("wait_time_ms", 0),
            }
            for name, data in self._metrics.items()
        }

    def get_health_status(self) -> dict:
        """获取健康状态"""
        issues = []
        for name, data in self._metrics.items():
            active_ratio = data.get("active_connections", 0) / max(
                data.get("total_connections", 1), 1
            )
            if active_ratio > 0.9:
                issues.append(f"{name}: 连接池接近耗尽 ({active_ratio:.1%})")

            wait_time = data.get("wait_time_ms", 0)
            if wait_time > 100:
                issues.append(f"{name}: 等待时间过长 ({wait_time}ms)")

        return {
            "healthy": len(issues) == 0,
            "issues": issues,
        }


class PerformanceOptimizer:
    """
    性能优化器

    综合管理缓存、批处理、连接池等优化组件。
    """

    def __init__(self):
        self._cache = LRUCache(CacheConfig(max_size=2000, ttl_seconds=600.0))
        self._batch_processor = BatchProcessor(batch_size=50, batch_timeout=0.05)
        self._pool_monitor = ConnectionPoolMonitor()
        self._initialized = False

    async def initialize(self):
        """初始化优化器"""
        if not self._initialized:
            await self._batch_processor.start()
            self._initialized = True
            logger.info("Performance optimizer initialized")

    async def shutdown(self):
        """关闭优化器"""
        if self._initialized:
            await self._batch_processor.stop()
            await self._cache.clear()
            self._initialized = False
            logger.info("Performance optimizer shutdown")

    def get_cache(self) -> LRUCache:
        """获取缓存实例"""
        return self._cache

    def get_batch_processor(self) -> BatchProcessor:
        """获取批处理器"""
        return self._batch_processor

    def get_pool_monitor(self) -> ConnectionPoolMonitor:
        """获取连接池监控"""
        return self._pool_monitor

    def get_all_stats(self) -> dict:
        """获取所有优化组件统计"""
        return {
            "cache": self._cache.get_stats(),
            "pools": self._pool_monitor.get_all_stats(),
            "pools_health": self._pool_monitor.get_health_status(),
        }


# 全局性能优化器实例
_global_optimizer: PerformanceOptimizer | None = None


def get_optimizer() -> PerformanceOptimizer:
    """获取全局性能优化器"""
    global _global_optimizer
    if _global_optimizer is None:
        _global_optimizer = PerformanceOptimizer()
    return _global_optimizer
