"""
评估结果缓存服务 - 2026 工业级标准

用于减少重复评估开销，支持：
- 内存缓存（默认）
- Redis 缓存（可选，支持 Cluster）
- 语义缓存（基于文本相似度匹配）
- 过期策略（TTL）
- 缓存统计（命中率、节省时间）

设计原则：
- 缓存键基于输入内容的哈希，确保相同输入产生相同的缓存键
- 支持评估器类型隔离，不同评估器的相同输入产生不同缓存键
- 提供缓存统计信息，便于监控缓存效果
- 支持缓存预热和缓存清理
- 优雅降级，Redis不可用时自动使用内存缓存
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass

from src.domain.services.text_analysis_service import text_analysis_service
from src.infra.cache.redis_cluster_manager import redis_cluster_manager
from src.schemas.evaluation import DomainResponse
from src.schemas.evaluation import EvaluationSchema

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """缓存条目"""
    response: DomainResponse
    timestamp: float
    ttl_seconds: float

    def is_expired(self) -> bool:
        """检查缓存是否过期"""
        return time.time() - self.timestamp > self.ttl_seconds


@dataclass
class CacheStats:
    """缓存统计信息"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    total_time_saved: float = 0.0

    @property
    def hit_rate(self) -> float:
        """计算命中率"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class EvaluationCacheService:
    """评估结果缓存服务"""

    def __init__(self, ttl_seconds: int = 3600, max_entries: int = 10000):
        """
        初始化缓存服务

        Args:
            ttl_seconds: 缓存过期时间（秒），默认 1 小时
            max_entries: 最大缓存条目数，超过后按 LRU 淘汰
        """
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._cache: dict[str, CacheEntry] = {}
        self._stats = CacheStats()
        self._redis_enabled = False
        self._semantic_cache_enabled = False
        self._semantic_threshold = 0.95

    def _generate_cache_key(self, request: EvaluationSchema) -> str:
        """
        生成缓存键

        基于评估器类型和输入内容的哈希生成唯一键
        """
        key_components = [
            request.type,
            str(request.id),
            str(request.payload.get("user_input")),
            str(request.payload.get("expected_output")),
            str(request.payload.get("actual_output")),
            str(request.payload.get("system_prompt")),
        ]
        key_string = "|".join(key_components)
        return hashlib.md5(key_string.encode()).hexdigest()

    def _generate_fuzzy_key(self, request: EvaluationSchema) -> str:
        """
        生成模糊缓存键（用于语义缓存）

        基于评估器类型和输入内容的标准化文本生成键
        """
        key_components = [
            request.type,
            str(request.payload.get("user_input")),
            str(request.payload.get("expected_output")),
        ]
        key_string = "|".join(key_components)
        return hashlib.md5(key_string.encode()).hexdigest()

    def get(self, request: EvaluationSchema) -> DomainResponse | None:
        """
        获取缓存结果

        优先级：内存缓存 > Redis 缓存 > 语义缓存

        Args:
            request: 评估请求

        Returns:
            缓存的评估结果，如果未命中或已过期则返回 None
        """
        cache_key = self._generate_cache_key(request)

        if cache_key in self._cache:
            entry = self._cache[cache_key]
            if entry.is_expired():
                del self._cache[cache_key]
                self._stats.evictions += 1
                self._stats.misses += 1
                return None

            self._stats.hits += 1
            return entry.response

        if self._redis_enabled:
            if redis_response := self._get_redis_cache(cache_key):
                self._stats.hits += 1
                self._cache[cache_key] = CacheEntry(
                    response=redis_response,
                    timestamp=time.time(),
                    ttl_seconds=self.ttl_seconds,
                )
                return redis_response

        if self._semantic_cache_enabled:
            return self._get_semantic_cache(request)

        self._stats.misses += 1
        return None

    def _get_semantic_cache(self, request: EvaluationSchema) -> DomainResponse | None:
        """
        获取语义缓存结果

        基于文本相似度匹配查找相似的缓存条目
        """
        user_input = request.payload.get("user_input", "")
        expected_output = request.payload.get("expected_output", "")

        for key, entry in self._cache.items():
            if entry.is_expired():
                continue

            cached_request = entry.response.data if entry.response.data else {}
            cached_input = cached_request.get("user_input", "")
            cached_expected = cached_request.get("expected_output", "")

            if not cached_input or not cached_expected:
                continue

            similarity = text_analysis_service.calculate_text_similarity(
                f"{user_input} {expected_output}",
                f"{cached_input} {cached_expected}",
            )

            if similarity >= self._semantic_threshold:
                self._stats.hits += 1
                logger.debug(f"语义缓存命中，相似度: {similarity:.4f}")
                return entry.response

        return None

    def set(self, request: EvaluationSchema, response: DomainResponse) -> None:
        """
        设置缓存结果

        Args:
            request: 评估请求
            response: 评估结果
        """
        cache_key = self._generate_cache_key(request)

        if len(self._cache) >= self.max_entries:
            self._evict_lru()

        self._cache[cache_key] = CacheEntry(
            response=response,
            timestamp=time.time(),
            ttl_seconds=self.ttl_seconds,
        )

        if self._redis_enabled:
            self._set_redis_cache(cache_key, response)

    def _evict_lru(self) -> None:
        """
        LRU 淘汰策略

        删除最早的缓存条目
        """
        if not self._cache:
            return

        oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].timestamp)
        del self._cache[oldest_key]
        self._stats.evictions += 1

    def _set_redis_cache(self, cache_key: str, response: DomainResponse) -> None:
        """
        设置 Redis 缓存

        Args:
            cache_key: 缓存键
            response: 评估结果
        """
        try:
            from src.schemas.evaluation import EvaluatorStatus

            cache_value = json.dumps({
                "score": response.score,
                "evaluation_status": response.evaluation_status.value if isinstance(response.evaluation_status, EvaluatorStatus) else response.evaluation_status,
                "text": response.text,
                "confidence": response.confidence,
                "data": response.data,
                "dimensions_evaluated": getattr(response, "dimensions_evaluated", None),
                "dimensions_skipped": getattr(response, "dimensions_skipped", None),
                "skip_reasons": getattr(response, "skip_reasons", None),
            })
            redis_cluster_manager.set_with_expiry(cache_key, cache_value, self.ttl_seconds)
        except Exception as e:
            logger.error(f"Redis 缓存设置失败: {e}")

    def _get_redis_cache(self, cache_key: str) -> DomainResponse | None:
        """
        获取 Redis 缓存

        Args:
            cache_key: 缓存键

        Returns:
            缓存的评估结果，如果未命中则返回 None
        """
        try:
            cache_value = redis_cluster_manager.get(cache_key)
            if cache_value:
                data = json.loads(cache_value)
                from src.schemas.evaluation import EvaluatorStatus

                status = data.get("evaluation_status")
                if isinstance(status, str):
                    status = EvaluatorStatus(status)

                return DomainResponse(
                    score=data.get("score"),
                    evaluation_status=status,
                    text=data.get("text"),
                    confidence=data.get("confidence"),
                    data=data.get("data"),
                )
        except Exception as e:
            logger.error(f"Redis 缓存获取失败: {e}")

        return None

    def enable_redis(self) -> None:
        """
        启用 Redis 缓存

        使用统一的 RedisClusterManager 进行分布式缓存管理
        """
        self._redis_enabled = redis_cluster_manager.is_connected()
        if self._redis_enabled:
            logger.info("Redis 缓存已启用")
        else:
            logger.warning("Redis 连接不可用，将使用内存缓存")
            self._redis_enabled = False

    def enable_semantic_cache(self, threshold: float = 0.95) -> None:
        """
        启用语义缓存

        Args:
            threshold: 语义相似度阈值，超过此值视为命中
        """
        self._semantic_cache_enabled = True
        self._semantic_threshold = threshold
        logger.info(f"语义缓存已启用，相似度阈值: {threshold}")

    def invalidate(self, request: EvaluationSchema) -> None:
        """
        使指定请求的缓存失效

        Args:
            request: 评估请求
        """
        cache_key = self._generate_cache_key(request)
        if cache_key in self._cache:
            del self._cache[cache_key]
        if self._redis_enabled:
            redis_cluster_manager.delete(cache_key)
        logger.debug(f"缓存已失效: {cache_key}")

    def invalidate_by_type(self, evaluator_type: str) -> None:
        """
        使指定类型评估器的所有缓存失效

        Args:
            evaluator_type: 评估器类型
        """
        keys_to_delete = [
            key for key in self._cache.keys()
            if key.startswith(evaluator_type[:8])
        ]
        for key in keys_to_delete:
            del self._cache[key]
        logger.info(f"已失效 {len(keys_to_delete)} 个 {evaluator_type} 类型的缓存")

    def clear(self) -> None:
        """
        清空所有缓存
        """
        self._cache.clear()
        if self._redis_enabled:
            redis_cluster_manager.flush_cache()
        logger.info("缓存已清空")

    def get_stats(self) -> CacheStats:
        """
        获取缓存统计信息

        Returns:
            缓存统计信息
        """
        return self._stats

    def reset_stats(self) -> None:
        """
        重置缓存统计信息
        """
        self._stats = CacheStats()
        logger.info("缓存统计已重置")

    def warmup(self, requests: list[EvaluationSchema], responses: list[DomainResponse]) -> None:
        """
        缓存预热

        Args:
            requests: 评估请求列表
            responses: 对应的评估结果列表
        """
        for request, response in zip(requests, responses):
            self.set(request, response)
        logger.info(f"缓存预热完成，共缓存 {len(requests)} 条记录")


evaluation_cache_service = EvaluationCacheService()
