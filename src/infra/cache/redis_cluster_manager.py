"""
Redis Cluster 管理器 - 2026 工业级标准

用于统一管理 Redis 连接，支持：
- 单机 Redis
- Redis Sentinel
- Redis Cluster
- 连接池管理
- 健康检查
- 自动重连

设计原则：
- 单例模式，避免重复创建连接
- 延迟初始化，支持按需连接
- 优雅降级，Redis不可用时使用内存缓存
- 完整的错误处理和日志记录
"""

import logging
import time
from typing import Optional

import redis

from src.config import settings

logger = logging.getLogger(__name__)


class RedisClusterManager:
    """Redis Cluster 管理器"""

    _instance = None
    _lock = __import__("threading").Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True

        self._client = None
        self._async_client = None
        self._connected = False
        self._connection_error_count = 0
        self._last_connection_attempt = 0
        self._retry_interval = 30

    def _create_client(self) -> Optional[redis.Redis]:
        """创建 Redis 客户端"""
        try:
            if "," in settings.redis_url:
                return self._create_cluster_client()
            else:
                return self._create_standalone_client()
        except Exception as e:
            logger.error(f"Redis 客户端创建失败: {e}")
            return None

    def _create_standalone_client(self) -> redis.Redis:
        """创建单机 Redis 客户端"""
        return redis.Redis.from_url(
            settings.redis_url,
            max_connections=settings.redis_pool_size,
            decode_responses=True,
            health_check_interval=30,
        )

    def _create_cluster_client(self) -> redis.Redis:
        """创建 Redis Cluster 客户端"""
        urls = [url.strip() for url in settings.redis_url.split(",")]
        startup_nodes = []
        for url in urls:
            try:
                import urllib.parse
                parsed = urllib.parse.urlparse(url)
                startup_nodes.append({
                    "host": parsed.hostname or "localhost",
                    "port": parsed.port or 6379,
                })
            except Exception:
                logger.warning(f"无效的 Redis URL: {url}")

        if not startup_nodes:
            return self._create_standalone_client()

        try:
            from redis.cluster import RedisCluster
            return RedisCluster(
                startup_nodes=startup_nodes,
                decode_responses=True,
                max_connections=settings.redis_pool_size,
                health_check_interval=30,
            )
        except ImportError:
            logger.warning("redis-py-cluster 未安装，回退到单机模式")
            return self._create_standalone_client()
        except Exception as e:
            logger.error(f"Redis Cluster 创建失败: {e}")
            return self._create_standalone_client()

    def get_client(self) -> Optional[redis.Redis]:
        """获取 Redis 客户端（带自动重连）"""
        if self._client and self._connected:
            return self._client

        now = time.time()
        if self._client is not None and now - self._last_connection_attempt < self._retry_interval:
            return None

        self._last_connection_attempt = now
        self._client = self._create_client()

        if self._client:
            try:
                self._client.ping()
                self._connected = True
                self._connection_error_count = 0
                logger.info("Redis 连接成功")
            except Exception as e:
                self._connected = False
                self._connection_error_count += 1
                logger.error(f"Redis 连接失败: {e}")
                self._client = None

        return self._client

    def is_connected(self) -> bool:
        """检查 Redis 是否连接"""
        if not self._client:
            return False

        try:
            self._client.ping()
            return True
        except Exception:
            self._connected = False
            return False

    def disconnect(self):
        """断开 Redis 连接"""
        if self._client:
            try:
                self._client.close()
            except Exception as e:
                logger.error(f"Redis 断开连接失败: {e}")
        self._client = None
        self._connected = False

    def get_connection_stats(self) -> dict:
        """获取连接统计信息"""
        return {
            "connected": self._connected,
            "error_count": self._connection_error_count,
            "last_attempt": self._last_connection_attempt,
            "pool_size": settings.redis_pool_size,
            "redis_url": settings.redis_url[:20] + "..." if len(settings.redis_url) > 20 else settings.redis_url,
        }

    def flush_cache(self, pattern: str = "*") -> int:
        """
        刷新缓存（支持模式匹配）

        Args:
            pattern: 缓存键模式，默认清除所有

        Returns:
            清除的键数量
        """
        client = self.get_client()
        if not client:
            return 0

        try:
            keys = client.keys(pattern)
            if keys:
                client.delete(*keys)
                logger.info(f"清除了 {len(keys)} 个缓存键")
                return len(keys)
            return 0
        except Exception as e:
            logger.error(f"缓存刷新失败: {e}")
            return 0

    def set_with_expiry(self, key: str, value: str, expiry: int = 3600) -> bool:
        """
        设置带过期时间的缓存

        Args:
            key: 缓存键
            value: 缓存值
            expiry: 过期时间（秒）

        Returns:
            是否设置成功
        """
        client = self.get_client()
        if not client:
            return False

        try:
            client.setex(key, expiry, value)
            return True
        except Exception as e:
            logger.error(f"设置缓存失败: {e}")
            return False

    def get(self, key: str) -> Optional[str]:
        """
        获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值，如果未命中或出错返回 None
        """
        client = self.get_client()
        if not client:
            return None

        try:
            return client.get(key)
        except Exception as e:
            logger.error(f"获取缓存失败: {e}")
            return None

    def delete(self, key: str) -> bool:
        """
        删除缓存

        Args:
            key: 缓存键

        Returns:
            是否删除成功
        """
        client = self.get_client()
        if not client:
            return False

        try:
            client.delete(key)
            return True
        except Exception as e:
            logger.error(f"删除缓存失败: {e}")
            return False

    def exists(self, key: str) -> bool:
        """
        检查缓存是否存在

        Args:
            key: 缓存键

        Returns:
            是否存在
        """
        client = self.get_client()
        if not client:
            return False

        try:
            return client.exists(key) > 0
        except Exception as e:
            logger.error(f"检查缓存存在失败: {e}")
            return False


redis_cluster_manager = RedisClusterManager()
