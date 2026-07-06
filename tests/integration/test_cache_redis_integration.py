"""
Redis Cluster 与缓存服务集成测试

验证 EvaluationCacheService 与 RedisClusterManager 的集成功能，包括：
- 内存缓存与 Redis 缓存的协同工作
- Redis 缓存的读写操作
- 缓存失效和清空操作
- 优雅降级机制（Redis 不可用时使用内存缓存）

注意：本测试需要 Redis 服务运行在本地
"""

import pytest


@pytest.mark.integration
class TestCacheRedisIntegration:
    """缓存与 Redis 集成测试"""

    def setup_method(self):
        """每个测试方法前重置状态"""
        from src.domain.services.evaluation_cache_service import evaluation_cache_service
        from src.infra.cache.redis_cluster_manager import redis_cluster_manager

        evaluation_cache_service.clear()
        evaluation_cache_service.reset_stats()
        evaluation_cache_service._redis_enabled = False

    def test_redis_cache_enable(self):
        """测试启用 Redis 缓存"""
        from src.domain.services.evaluation_cache_service import evaluation_cache_service
        from src.infra.cache.redis_cluster_manager import redis_cluster_manager

        if redis_cluster_manager.is_connected():
            evaluation_cache_service.enable_redis()
            assert evaluation_cache_service._redis_enabled is True
        else:
            evaluation_cache_service.enable_redis()
            assert evaluation_cache_service._redis_enabled is False

    def test_cache_write_read_with_redis(self):
        """测试通过缓存服务写入和读取 Redis"""
        from src.domain.services.evaluation_cache_service import evaluation_cache_service, EvaluationCacheService
        from src.infra.cache.redis_cluster_manager import redis_cluster_manager
        from src.schemas.evaluation import DomainResponse, EvaluationSchema, EvaluatorStatus

        if not redis_cluster_manager.is_connected():
            pytest.skip("Redis 不可用，跳过测试")

        evaluation_cache_service.enable_redis()

        request = EvaluationSchema(
            id="test-redis-write-read",
            type="general",
            payload={"user_input": "测试 Redis", "expected_output": "期望", "actual_output": "实际"},
        )
        response = DomainResponse(
            score=0.9,
            evaluation_status=EvaluatorStatus.SUCCESS,
            text="测试结果",
        )

        evaluation_cache_service.set(request, response)

        redis_cluster_manager.disconnect()
        evaluation_cache_service._redis_enabled = False
        evaluation_cache_service.clear()

        cached = evaluation_cache_service.get(request)
        assert cached is None

        redis_cluster_manager.get_client()
        evaluation_cache_service.enable_redis()

        cached = evaluation_cache_service.get(request)
        assert cached is not None
        assert cached.score == 0.9

    def test_cache_invalidate_with_redis(self):
        """测试缓存失效操作同步到 Redis"""
        from src.domain.services.evaluation_cache_service import evaluation_cache_service
        from src.infra.cache.redis_cluster_manager import redis_cluster_manager
        from src.schemas.evaluation import DomainResponse, EvaluationSchema, EvaluatorStatus

        if not redis_cluster_manager.is_connected():
            pytest.skip("Redis 不可用，跳过测试")

        evaluation_cache_service.enable_redis()

        request = EvaluationSchema(
            id="test-redis-invalidate",
            type="general",
            payload={"user_input": "测试失效", "expected_output": "期望", "actual_output": "实际"},
        )
        response = DomainResponse(
            score=0.85,
            evaluation_status=EvaluatorStatus.SUCCESS,
            text="测试",
        )

        evaluation_cache_service.set(request, response)
        assert evaluation_cache_service.get(request) is not None

        evaluation_cache_service.invalidate(request)

        assert evaluation_cache_service.get(request) is None

        redis_cluster_manager.disconnect()
        evaluation_cache_service._redis_enabled = False
        evaluation_cache_service.clear()

    def test_cache_clear_with_redis(self):
        """测试清空缓存操作同步到 Redis"""
        from src.domain.services.evaluation_cache_service import evaluation_cache_service
        from src.infra.cache.redis_cluster_manager import redis_cluster_manager
        from src.schemas.evaluation import DomainResponse, EvaluationSchema, EvaluatorStatus

        if not redis_cluster_manager.is_connected():
            pytest.skip("Redis 不可用，跳过测试")

        evaluation_cache_service.enable_redis()

        request = EvaluationSchema(
            id="test-redis-clear",
            type="general",
            payload={"user_input": "测试清空", "expected_output": "期望", "actual_output": "实际"},
        )
        response = DomainResponse(
            score=0.85,
            evaluation_status=EvaluatorStatus.SUCCESS,
            text="测试",
        )

        evaluation_cache_service.set(request, response)
        assert evaluation_cache_service.get(request) is not None

        evaluation_cache_service.clear()

        assert evaluation_cache_service.get(request) is None

        redis_cluster_manager.disconnect()
        evaluation_cache_service._redis_enabled = False

    def test_graceful_degradation_when_redis_unavailable(self):
        """测试 Redis 不可用时优雅降级到内存缓存"""
        from src.domain.services.evaluation_cache_service import evaluation_cache_service
        from src.infra.cache.redis_cluster_manager import redis_cluster_manager
        from src.schemas.evaluation import DomainResponse, EvaluationSchema, EvaluatorStatus

        redis_cluster_manager.disconnect()
        evaluation_cache_service._redis_enabled = False

        request = EvaluationSchema(
            id="test-degradation",
            type="general",
            payload={"user_input": "测试降级", "expected_output": "期望", "actual_output": "实际"},
        )
        response = DomainResponse(
            score=0.9,
            evaluation_status=EvaluatorStatus.SUCCESS,
            text="降级测试",
        )

        evaluation_cache_service.set(request, response)
        cached = evaluation_cache_service.get(request)

        assert cached is not None
        assert cached.score == 0.9

    def test_redis_connection_stats(self):
        """测试 Redis 连接统计信息"""
        from src.infra.cache.redis_cluster_manager import redis_cluster_manager

        stats = redis_cluster_manager.get_connection_stats()
        assert isinstance(stats, dict)
        assert "connected" in stats
        assert "error_count" in stats
        assert "pool_size" in stats

    def test_redis_set_get_delete(self):
        """测试 Redis 基本操作"""
        from src.infra.cache.redis_cluster_manager import redis_cluster_manager

        if not redis_cluster_manager.is_connected():
            pytest.skip("Redis 不可用，跳过测试")

        assert redis_cluster_manager.set_with_expiry("integration-test-key", "test-value", 60)
        assert redis_cluster_manager.get("integration-test-key") == "test-value"
        assert redis_cluster_manager.delete("integration-test-key")
        assert redis_cluster_manager.get("integration-test-key") is None