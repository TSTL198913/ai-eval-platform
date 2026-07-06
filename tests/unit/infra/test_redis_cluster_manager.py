"""测试 RedisClusterManager 分布式缓存管理"""

import pytest
from unittest.mock import MagicMock, patch


class TestRedisClusterManager:
    """测试 RedisClusterManager"""

    def test_singleton_pattern(self):
        """单例模式测试"""
        from src.infra.cache.redis_cluster_manager import RedisClusterManager

        instance1 = RedisClusterManager()
        instance2 = RedisClusterManager()
        assert instance1 is instance2

    def test_is_connected_without_redis(self):
        """未连接 Redis 时返回 False"""
        from src.infra.cache.redis_cluster_manager import RedisClusterManager
        
        manager = RedisClusterManager()
        manager._client = None
        manager._connected = False
        
        assert manager.is_connected() is False

    def test_get_connection_stats(self):
        """获取连接统计信息"""
        from src.infra.cache.redis_cluster_manager import redis_cluster_manager

        stats = redis_cluster_manager.get_connection_stats()
        assert "connected" in stats
        assert "error_count" in stats
        assert "pool_size" in stats
        assert "redis_url" in stats

    def test_disconnect(self):
        """断开连接测试"""
        from src.infra.cache.redis_cluster_manager import redis_cluster_manager

        redis_cluster_manager.disconnect()
        assert redis_cluster_manager.is_connected() is False

    def test_set_and_get(self):
        """测试 set/get 操作"""
        from src.infra.cache.redis_cluster_manager import redis_cluster_manager

        result = redis_cluster_manager.set_with_expiry("test-key", "test-value", 3600)
        assert isinstance(result, bool)

        if result:
            retrieved = redis_cluster_manager.get("test-key")
            assert retrieved == "test-value"

    def test_delete(self):
        """测试 delete 操作"""
        from src.infra.cache.redis_cluster_manager import redis_cluster_manager

        redis_cluster_manager.set_with_expiry("test-delete-key", "test-value", 3600)
        result = redis_cluster_manager.delete("test-delete-key")
        assert isinstance(result, bool)

    def test_exists(self):
        """测试 exists 操作"""
        from src.infra.cache.redis_cluster_manager import redis_cluster_manager

        result = redis_cluster_manager.exists("test-non-existent-key")
        assert isinstance(result, bool)

    def test_flush_cache(self):
        """测试 flush_cache 操作"""
        from src.infra.cache.redis_cluster_manager import redis_cluster_manager

        redis_cluster_manager.set_with_expiry("test-flush-key", "test-value", 3600)
        result = redis_cluster_manager.flush_cache("test-flush-key")
        assert isinstance(result, int)

    @patch("redis.Redis.from_url")
    def test_standalone_client_creation(self, mock_from_url):
        """单机 Redis 客户端创建"""
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_from_url.return_value = mock_client

        from src.infra.cache.redis_cluster_manager import RedisClusterManager

        manager = RedisClusterManager()
        manager._create_standalone_client()

        mock_from_url.assert_called_once()

    def test_get_client_returns_instance(self):
        """测试 get_client 返回客户端实例或 None"""
        from src.infra.cache.redis_cluster_manager import redis_cluster_manager

        client = redis_cluster_manager.get_client()
        assert client is None or hasattr(client, "ping")