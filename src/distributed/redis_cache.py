"""Redis缓存服务 - 提供统一的Redis连接和操作接口

2026工业级标准实现：
1. Redis连接池管理 - 复用连接，避免频繁创建
2. 熔断器状态持久化 - 支持分布式状态共享
3. 分布式锁 - 防止多个实例同时修改状态
4. 健康检查 - 自动检测Redis可用性
5. 故障降级 - Redis不可用时自动降级到内存存储
6. 连接重试 - 定期尝试重新连接Redis
"""

import json
import logging
import threading
import time
from typing import Optional

import redis

from src.config import get_settings

logger = logging.getLogger(__name__)


class RedisCache:
    """Redis缓存服务"""

    _instance: Optional["RedisCache"] = None
    _instance_lock = threading.Lock()

    def __init__(self):
        """初始化Redis缓存服务"""
        self._settings = get_settings()
        self._client: redis.Redis | None = None
        self._connected = False
        self._lock = threading.RLock()
        self._memory_cache: dict[str, dict] = {}
        self._memory_cache_lock = threading.RLock()
        self._last_reconnect_attempt: float = 0.0
        self._reconnect_interval: float = 30.0
        self._init_client()

    @classmethod
    def get_instance(cls) -> "RedisCache":
        """获取单例（线程安全双重检查锁定）"""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _init_client(self):
        """初始化Redis客户端"""
        try:
            self._client = redis.Redis.from_url(
                self._settings.redis_url,
                max_connections=self._settings.redis_pool_size,
                decode_responses=True,
            )
            self._client.ping()
            self._connected = True
            logger.info(f"Redis连接成功: {self._settings.redis_url}")
        except Exception as e:
            logger.warning(f"Redis连接失败，降级到内存模式: {e}")
            self._connected = False

    def _try_reconnect(self):
        """尝试重新连接Redis"""
        now = time.time()
        if now - self._last_reconnect_attempt < self._reconnect_interval:
            return

        self._last_reconnect_attempt = now
        logger.info("尝试重新连接Redis...")
        try:
            self._client = redis.Redis.from_url(
                self._settings.redis_url,
                max_connections=self._settings.redis_pool_size,
                decode_responses=True,
            )
            self._client.ping()
            self._connected = True
            logger.info(f"Redis重新连接成功: {self._settings.redis_url}")
        except Exception as e:
            logger.debug(f"Redis重新连接失败: {e}")

    @property
    def client(self) -> redis.Redis | None:
        """获取Redis客户端（带自动重连）"""
        if not self._connected:
            self._try_reconnect()
        return self._client

    @property
    def is_connected(self) -> bool:
        """检查Redis是否连接"""
        if not self._connected:
            self._try_reconnect()
        return self._connected

    def health_check(self) -> bool:
        """健康检查"""
        if not self._client:
            return False
        try:
            self._client.ping()
            self._connected = True
            return True
        except Exception:
            self._connected = False
            return False

    def get(self, key: str) -> str | None:
        """获取值（降级到内存缓存）"""
        if self._connected and self._client:
            try:
                return self._client.get(key)
            except Exception as e:
                logger.error(f"Redis get失败，降级到内存: {e}")
                self._connected = False

        with self._memory_cache_lock:
            cached = self._memory_cache.get(key)
            if cached:
                if cached.get("expire_at") and time.time() > cached["expire_at"]:
                    del self._memory_cache[key]
                    return None
                return cached.get("value")
            return None

    def set(self, key: str, value: str, ex: int | None = None):
        """设置值（降级到内存缓存）"""
        if self._connected and self._client:
            try:
                self._client.set(key, value, ex=ex)
                return
            except Exception as e:
                logger.error(f"Redis set失败，降级到内存: {e}")
                self._connected = False

        with self._memory_cache_lock:
            self._memory_cache[key] = {"value": value, "expire_at": time.time() + ex if ex else None}

    def set_json(self, key: str, value: dict, ex: int | None = None):
        """设置JSON值（降级到内存缓存）"""
        if self._connected and self._client:
            try:
                self._client.set(key, json.dumps(value), ex=ex)
                return
            except Exception as e:
                logger.error(f"Redis set_json失败，降级到内存: {e}")
                self._connected = False

        with self._memory_cache_lock:
            self._memory_cache[key] = {"value": value, "expire_at": time.time() + ex if ex else None}

    def get_json(self, key: str) -> dict | None:
        """获取JSON值（降级到内存缓存）"""
        if self._connected and self._client:
            try:
                data = self._client.get(key)
                if data:
                    return json.loads(data)
                return None
            except Exception as e:
                logger.error(f"Redis get_json失败，降级到内存: {e}")
                self._connected = False

        with self._memory_cache_lock:
            cached = self._memory_cache.get(key)
            if cached:
                if cached.get("expire_at") and time.time() > cached["expire_at"]:
                    del self._memory_cache[key]
                    return None
                return cached.get("value")
            return None

    def delete(self, key: str):
        """删除键（降级到内存缓存）"""
        if self._connected and self._client:
            try:
                self._client.delete(key)
                return
            except Exception as e:
                logger.error(f"Redis delete失败，降级到内存: {e}")
                self._connected = False

        with self._memory_cache_lock:
            self._memory_cache.pop(key, None)

    def incr(self, key: str) -> int | None:
        """原子递增（降级到内存缓存）"""
        if self._connected and self._client:
            try:
                return self._client.incr(key)
            except Exception as e:
                logger.error(f"Redis incr失败，降级到内存: {e}")
                self._connected = False

        with self._memory_cache_lock:
            if key not in self._memory_cache:
                self._memory_cache[key] = {"value": 0}
            self._memory_cache[key]["value"] += 1
            return self._memory_cache[key]["value"]

    def decr(self, key: str) -> int | None:
        """原子递减（降级到内存缓存）"""
        if self._connected and self._client:
            try:
                return self._client.decr(key)
            except Exception as e:
                logger.error(f"Redis decr失败，降级到内存: {e}")
                self._connected = False

        with self._memory_cache_lock:
            if key not in self._memory_cache:
                self._memory_cache[key] = {"value": 0}
            self._memory_cache[key]["value"] -= 1
            return self._memory_cache[key]["value"]

    def exists(self, key: str) -> bool:
        """检查键是否存在（降级到内存缓存）"""
        if self._connected and self._client:
            try:
                return self._client.exists(key)
            except Exception as e:
                logger.error(f"Redis exists失败，降级到内存: {e}")
                self._connected = False

        with self._memory_cache_lock:
            cached = self._memory_cache.get(key)
            if cached:
                if cached.get("expire_at") and time.time() > cached["expire_at"]:
                    del self._memory_cache[key]
                    return False
                return True
            return False

    def acquire_lock(self, lock_key: str, timeout: int = 10) -> bool:
        """获取分布式锁（降级到本地锁）"""
        if self._connected and self._client:
            try:
                return bool(self._client.set(lock_key, "1", nx=True, ex=timeout))
            except Exception as e:
                logger.error(f"Redis acquire_lock失败，降级到本地锁: {e}")
                self._connected = False

        with self._memory_cache_lock:
            if lock_key in self._memory_cache:
                return False
            self._memory_cache[lock_key] = {"value": "1", "expire_at": time.time() + timeout}
            return True

    def release_lock(self, lock_key: str):
        """释放分布式锁（降级到本地锁）"""
        if self._connected and self._client:
            try:
                self._client.delete(lock_key)
                return
            except Exception as e:
                logger.error(f"Redis release_lock失败，降级到本地锁: {e}")
                self._connected = False

        with self._memory_cache_lock:
            self._memory_cache.pop(lock_key, None)

    def get_circuit_breaker_state(self, breaker_name: str) -> dict | None:
        """获取熔断器状态（降级到内存缓存）"""
        key = f"circuit_breaker:{breaker_name}"
        return self.get_json(key)

    def set_circuit_breaker_state(self, breaker_name: str, state_data: dict, ttl: int = 3600):
        """设置熔断器状态（降级到内存缓存）"""
        key = f"circuit_breaker:{breaker_name}"
        self.set_json(key, state_data, ex=ttl)

    def delete_circuit_breaker_state(self, breaker_name: str):
        """删除熔断器状态（降级到内存缓存）"""
        key = f"circuit_breaker:{breaker_name}"
        self.delete(key)

    def increment_failure_count(self, breaker_name: str) -> int | None:
        """原子递增失败计数（降级到内存缓存）"""
        key = f"circuit_breaker:{breaker_name}:failure_count"
        return self.incr(key)

    def increment_success_count(self, breaker_name: str) -> int | None:
        """原子递增成功计数（降级到内存缓存）"""
        key = f"circuit_breaker:{breaker_name}:success_count"
        return self.incr(key)

    def reset_counts(self, breaker_name: str):
        """重置计数（降级到内存缓存）"""
        failure_key = f"circuit_breaker:{breaker_name}:failure_count"
        success_key = f"circuit_breaker:{breaker_name}:success_count"
        self.delete(failure_key)
        self.delete(success_key)


redis_cache = RedisCache()
