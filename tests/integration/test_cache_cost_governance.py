"""
缓存与成本治理集成测试
覆盖 EvaluationCache 和 CostGovernance 核心功能
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from src.infra.cache import EvaluationCache, cached, batch_insert
from src.infra.cost_governance import CostGovernance, CostRecord, TokenUsage, CostMetrics


class TestEvaluationCacheIntegration:
    """评估缓存集成测试"""

    def test_cache_basic_operations(self):
        """测试缓存基本操作"""
        cache = EvaluationCache(ttl_seconds=60)

        # 测试设置和获取
        cache.set("key1", {"data": "value1"})
        result = cache.get("key1")
        assert result == {"data": "value1"}

        # 测试覆盖已有值
        cache.set("key1", {"data": "value2"})
        result = cache.get("key1")
        assert result == {"data": "value2"}

    def test_cache_ttl_expiry(self):
        """测试缓存TTL过期"""
        cache = EvaluationCache(ttl_seconds=1)

        cache.set("temp_key", {"data": "temp"})
        assert cache.get("temp_key") is not None

        # 等待过期
        time.sleep(1.1)
        assert cache.get("temp_key") is None

    def test_cache_lru_eviction(self):
        """测试LRU淘汰策略"""
        cache = EvaluationCache(ttl_seconds=60, max_size=3)

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        # 访问key1使其变为最近使用
        cache.get("key1")

        # 添加新key，key2应该被淘汰
        cache.set("key4", "value4")

        # key1应该还在
        assert cache.get("key1") == "value1"
        # key2应该被淘汰
        assert cache.get("key2") is None
        # key3和key4应该在
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"

    def test_cache_invalidate(self):
        """测试缓存失效"""
        cache = EvaluationCache(ttl_seconds=60)

        cache.set("delete_key", {"data": "delete"})
        cache.invalidate("delete_key")

        assert cache.get("delete_key") is None

    def test_cache_clear(self):
        """测试清空缓存"""
        cache = EvaluationCache(ttl_seconds=60)

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()

        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.size() == 0

    def test_cache_stats(self):
        """测试缓存统计"""
        cache = EvaluationCache(ttl_seconds=60)

        cache.set("key1", "value1")
        cache.get("key1")  # hit
        cache.get("key2")  # miss

        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1

    def test_cache_zero_max_size(self):
        """测试max_size为0时不存储"""
        cache = EvaluationCache(ttl_seconds=60, max_size=0)

        cache.set("key1", "value1")
        assert cache.get("key1") is None
        assert cache.size() == 0

    def test_cache_thread_safety(self):
        """测试缓存线程安全"""
        import threading

        cache = EvaluationCache(ttl_seconds=60, max_size=1000)
        errors = []

        def worker(start, end):
            try:
                for i in range(start, end):
                    cache.set(f"key_{i}", f"value_{i}")
                    cache.get(f"key_{i}")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=worker, args=(0, 100)),
            threading.Thread(target=worker, args=(100, 200)),
            threading.Thread(target=worker, args=(200, 300)),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert cache.size() <= 1000  # 不超过容量限制


class TestCostGovernanceIntegration:
    """成本治理集成测试"""

    def test_cost_calculation(self):
        """测试成本计算"""
        governance = CostGovernance()

        # 测试GPT-4成本
        cost = governance.calculate_cost("gpt-4", 1000, 500)
        expected = 1000 * 0.00003 + 500 * 0.00006
        assert cost == expected

        # 测试默认成本
        cost = governance.calculate_cost("unknown-model", 1000, 500)
        expected = 1000 * 0.000002 + 500 * 0.000002
        assert cost == expected

    def test_record_usage(self):
        """测试记录使用"""
        governance = CostGovernance()

        record = governance.record_usage(
            record_id="test_001",
            model_name="gpt-4",
            prompt_tokens=1000,
            completion_tokens=500,
            latency_ms=150.0,
        )

        assert record.record_id == "test_001"
        assert record.model_name == "gpt-4"
        assert record.usage.prompt_tokens == 1000
        assert record.usage.completion_tokens == 500
        assert record.usage.total_tokens == 1500
        assert record.cost_usd > 0
        assert record.latency_ms == 150.0

    def test_get_metrics_empty(self):
        """测试空数据获取指标"""
        governance = CostGovernance()

        metrics = governance.get_metrics()

        assert isinstance(metrics, CostMetrics)
        assert metrics.daily_cost_usd == 0
        assert metrics.total_requests == 0

    def test_get_metrics_with_data(self):
        """测试有数据获取指标"""
        governance = CostGovernance()

        governance.record_usage(
            record_id="test_001",
            model_name="gpt-4",
            prompt_tokens=1000,
            completion_tokens=500,
            latency_ms=100.0,
        )
        governance.record_usage(
            record_id="test_002",
            model_name="claude-3",
            prompt_tokens=2000,
            completion_tokens=1000,
            latency_ms=200.0,
        )

        metrics = governance.get_metrics()

        assert metrics.total_requests == 2
        assert metrics.avg_latency_ms == 150.0
        assert metrics.daily_cost_usd > 0

    def test_check_budget(self):
        """测试预算检查"""
        governance = CostGovernance()

        result = governance.check_budget()

        assert "daily_budget_ok" in result
        assert "daily_usage_percent" in result
        assert result["daily_budget_ok"] is True
        assert result["daily_usage_percent"] >= 0

    def test_get_top_models_by_cost(self):
        """测试按成本获取模型排名"""
        governance = CostGovernance()

        governance.record_usage(
            record_id="test_001",
            model_name="gpt-4",
            prompt_tokens=10000,
            completion_tokens=5000,
        )
        governance.record_usage(
            record_id="test_002",
            model_name="claude-3",
            prompt_tokens=10000,
            completion_tokens=5000,
        )

        top_models = governance.get_top_models_by_cost(limit=5)

        assert len(top_models) <= 5
        assert all("model_name" in m for m in top_models)
        assert all("total_cost" in m for m in top_models)

    def test_get_top_requests_by_latency(self):
        """测试按延迟获取请求排名"""
        governance = CostGovernance()

        governance.record_usage(
            record_id="slow_001",
            model_name="gpt-4",
            latency_ms=500.0,
        )
        governance.record_usage(
            record_id="fast_001",
            model_name="gpt-4",
            latency_ms=100.0,
        )

        top_requests = governance.get_top_requests_by_latency(limit=10)

        assert len(top_requests) == 2
        # 第一个应该是延迟最高的
        assert top_requests[0].latency_ms == 500.0


class TestCacheAndCostIntegration:
    """缓存与成本治理集成测试"""

    def test_cache_cost_combined_flow(self):
        """测试缓存和成本治理组合流程"""
        cache = EvaluationCache(ttl_seconds=3600)
        governance = CostGovernance()

        request_id = "eval_001"

        # 检查缓存
        cached_result = cache.get(request_id)
        if cached_result is None:
            # 记录成本
            governance.record_usage(
                record_id=request_id,
                model_name="gpt-4",
                prompt_tokens=1000,
                completion_tokens=500,
                latency_ms=150.0,
            )

            # 缓存结果
            metrics = governance.get_metrics()
            cache.set(request_id, {
                "metrics": {
                    "total_requests": metrics.total_requests,
                    "daily_cost": metrics.daily_cost_usd,
                }
            })

        # 验证结果
        cached_result = cache.get(request_id)
        assert cached_result is not None

        metrics = governance.get_metrics()
        assert metrics.total_requests == 1

    def test_batch_cache_operations(self):
        """测试批量缓存操作"""
        cache = EvaluationCache(ttl_seconds=60)

        # 批量设置
        for i in range(100):
            cache.set(f"batch_key_{i}", {"index": i})

        # 验证大小
        assert cache.size() == 100

        # 批量获取
        for i in range(50):
            result = cache.get(f"batch_key_{i}")
            assert result is not None

        # 验证统计
        stats = cache.get_stats()
        assert stats["hits"] >= 50


class TestCostRecordModel:
    """成本记录模型测试"""

    def test_token_usage_model(self):
        """测试Token使用模型"""
        usage = TokenUsage(
            prompt_tokens=1000,
            completion_tokens=500,
        )

        assert usage.prompt_tokens == 1000
        assert usage.completion_tokens == 500
        assert usage.total_tokens == 0  # 需要手动计算

    def test_cost_record_model(self):
        """测试成本记录模型"""
        record = CostRecord(
            record_id="test_001",
            model_name="gpt-4",
            usage=TokenUsage(prompt_tokens=1000, completion_tokens=500),
            cost_usd=0.06,
            latency_ms=150.0,
        )

        assert record.record_id == "test_001"
        assert record.model_name == "gpt-4"
        assert record.cost_usd == 0.06
        assert record.latency_ms == 150.0
        assert record.request_type == "evaluation"

    def test_cost_metrics_model(self):
        """测试成本指标模型"""
        metrics = CostMetrics(
            daily_cost_usd=100.0,
            weekly_cost_usd=500.0,
            monthly_cost_usd=2000.0,
            avg_latency_ms=150.0,
            p50_latency_ms=100.0,
            p95_latency_ms=300.0,
            p99_latency_ms=500.0,
            total_requests=1000,
            avg_tokens_per_request=1500.0,
        )

        assert metrics.daily_cost_usd == 100.0
        assert metrics.total_requests == 1000
        assert metrics.avg_latency_ms == 150.0