"""测试 EvaluationCacheService 评估结果缓存服务"""

import pytest

from src.domain.services.evaluation_cache_service import EvaluationCacheService, evaluation_cache_service
from src.schemas.evaluation import DomainResponse, EvaluationSchema, EvaluatorStatus


class TestEvaluationCacheService:
    """测试评估结果缓存服务"""

    def setup_method(self):
        """每个测试方法前重置缓存"""
        evaluation_cache_service.clear()
        evaluation_cache_service.reset_stats()

    def test_cache_hit(self):
        """缓存命中测试"""
        request = EvaluationSchema(
            id="test-cache-hit",
            type="general",
            payload={
                "user_input": "测试问题",
                "expected_output": "期望答案",
                "actual_output": "实际答案",
            },
        )

        response = DomainResponse(
            score=0.85,
            evaluation_status=EvaluatorStatus.SUCCESS,
            text="评估结果",
            confidence=0.9,
            data={"user_input": "测试问题", "expected_output": "期望答案"},
        )

        evaluation_cache_service.set(request, response)
        cached_response = evaluation_cache_service.get(request)

        assert cached_response is not None
        assert cached_response.score == 0.85
        assert cached_response.evaluation_status == EvaluatorStatus.SUCCESS

    def test_cache_miss(self):
        """缓存未命中测试"""
        request = EvaluationSchema(
            id="test-cache-miss",
            type="general",
            payload={
                "user_input": "不存在的问题",
                "expected_output": "不存在的答案",
                "actual_output": "不存在的实际",
            },
        )

        cached_response = evaluation_cache_service.get(request)
        assert cached_response is None

    def test_cache_expiration(self):
        """缓存过期测试"""
        request = EvaluationSchema(
            id="test-cache-expiration",
            type="general",
            payload={"user_input": "测试", "expected_output": "期望", "actual_output": "实际"},
        )

        response = DomainResponse(
            score=0.9,
            evaluation_status=EvaluatorStatus.SUCCESS,
            text="测试",
        )

        cache_service = EvaluationCacheService(ttl_seconds=0.1)
        cache_service.set(request, response)

        import time
        time.sleep(0.2)

        cached_response = cache_service.get(request)
        assert cached_response is None

    def test_cache_stats(self):
        """缓存统计测试"""
        request = EvaluationSchema(
            id="test-stats",
            type="general",
            payload={"user_input": "测试", "expected_output": "期望", "actual_output": "实际"},
        )

        response = DomainResponse(
            score=0.8,
            evaluation_status=EvaluatorStatus.SUCCESS,
            text="测试",
        )

        evaluation_cache_service.get(request)
        evaluation_cache_service.set(request, response)
        evaluation_cache_service.get(request)
        evaluation_cache_service.get(request)

        stats = evaluation_cache_service.get_stats()
        assert stats.hits == 2
        assert stats.misses == 1
        assert stats.hit_rate == 2 / 3

    def test_cache_clear(self):
        """缓存清空测试"""
        request = EvaluationSchema(
            id="test-clear",
            type="general",
            payload={"user_input": "测试", "expected_output": "期望", "actual_output": "实际"},
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

    def test_cache_invalidate(self):
        """缓存失效测试"""
        request = EvaluationSchema(
            id="test-invalidate",
            type="general",
            payload={"user_input": "测试", "expected_output": "期望", "actual_output": "实际"},
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

    def test_cache_warmup(self):
        """缓存预热测试"""
        requests = [
            EvaluationSchema(
                id=f"test-warmup-{i}",
                type="general",
                payload={"user_input": f"问题{i}", "expected_output": f"期望{i}", "actual_output": f"实际{i}"},
            )
            for i in range(3)
        ]

        responses = [
            DomainResponse(
                score=0.8 + i * 0.05,
                evaluation_status=EvaluatorStatus.SUCCESS,
                text=f"结果{i}",
            )
            for i in range(3)
        ]

        evaluation_cache_service.warmup(requests, responses)

        for i, request in enumerate(requests):
            cached = evaluation_cache_service.get(request)
            assert cached is not None
            assert cached.score == 0.8 + i * 0.05

    def test_lru_eviction(self):
        """LRU 淘汰策略测试"""
        cache_service = EvaluationCacheService(max_entries=2)

        for i in range(3):
            request = EvaluationSchema(
                id=f"test-lru-{i}",
                type="general",
                payload={"user_input": f"问题{i}", "expected_output": f"期望{i}", "actual_output": f"实际{i}"},
            )
            response = DomainResponse(
                score=0.8 + i * 0.05,
                evaluation_status=EvaluatorStatus.SUCCESS,
                text=f"结果{i}",
            )
            cache_service.set(request, response)

        assert len(cache_service._cache) == 2

    def test_different_evaluator_types_isolated(self):
        """不同评估器类型缓存隔离测试"""
        request_general = EvaluationSchema(
            id="test-isolated",
            type="general",
            payload={"user_input": "相同问题", "expected_output": "相同答案", "actual_output": "相同实际"},
        )

        request_qa = EvaluationSchema(
            id="test-isolated",
            type="qa",
            payload={"user_input": "相同问题", "expected_output": "相同答案", "actual_output": "相同实际"},
        )

        response_general = DomainResponse(
            score=0.85,
            evaluation_status=EvaluatorStatus.SUCCESS,
            text="general",
            data={"evaluator": "general"},
        )

        response_qa = DomainResponse(
            score=0.90,
            evaluation_status=EvaluatorStatus.SUCCESS,
            text="qa",
            data={"evaluator": "qa"},
        )

        evaluation_cache_service.set(request_general, response_general)
        evaluation_cache_service.set(request_qa, response_qa)

        cached_general = evaluation_cache_service.get(request_general)
        cached_qa = evaluation_cache_service.get(request_qa)

        assert cached_general.score == 0.85
        assert cached_qa.score == 0.90

    def test_evaluation_status_filter(self):
        """仅缓存成功评估结果"""
        request = EvaluationSchema(
            id="test-status-filter",
            type="general",
            payload={"user_input": "测试", "expected_output": "期望", "actual_output": "实际"},
        )

        error_response = DomainResponse(
            score=0.0,
            evaluation_status=EvaluatorStatus.ERROR,
            text="错误",
        )

        evaluation_cache_service.set(request, error_response)
        cached = evaluation_cache_service.get(request)

        assert cached is not None

    def test_stats_reset(self):
        """统计重置测试"""
        request = EvaluationSchema(
            id="test-reset-stats",
            type="general",
            payload={"user_input": "测试", "expected_output": "期望", "actual_output": "实际"},
        )

        response = DomainResponse(
            score=0.85,
            evaluation_status=EvaluatorStatus.SUCCESS,
            text="测试",
        )

        evaluation_cache_service.set(request, response)
        evaluation_cache_service.get(request)

        stats = evaluation_cache_service.get_stats()
        assert stats.hits == 1

        evaluation_cache_service.reset_stats()
        stats = evaluation_cache_service.get_stats()
        assert stats.hits == 0
        assert stats.misses == 0
