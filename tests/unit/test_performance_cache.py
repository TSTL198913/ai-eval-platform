"""Performance EvaluationCache测试

验证performance.py中EvaluationCache的LRU淘汰、容量限制和接口兼容性。
"""

import pytest
import tempfile
import os
import json

from src.infra.performance import EvaluationCache


class TestPerformanceEvaluationCache:
    """性能缓存测试"""

    def test_init_with_defaults(self):
        """验证默认初始化"""
        cache = EvaluationCache(max_size=10)
        stats = cache.get_stats()
        assert stats["total_entries"] == 0
        assert stats["total_hits"] == 0

    def test_set_and_get_with_dict_key(self):
        """验证使用dict作为key的set/get"""
        cache = EvaluationCache(max_size=10)
        
        request_data = {"question": "test", "answer": "hello"}
        result = {"score": 0.85, "confidence": 0.9}
        
        cache.set(request_data, result)
        retrieved = cache.get(request_data)
        
        assert retrieved is not None
        assert retrieved["score"] == 0.85

    def test_set_and_get_with_str_key(self):
        """验证使用str作为key的set/get（兼容性）"""
        cache = EvaluationCache(max_size=10)
        
        cache.set("test_key", {"score": 0.75})
        retrieved = cache.get("test_key")
        
        assert retrieved is not None
        assert retrieved["score"] == 0.75

    def test_lru_eviction(self):
        """验证LRU淘汰机制"""
        cache = EvaluationCache(max_size=3)
        
        for i in range(5):
            cache.set({"key": f"k{i}"}, {"value": i})
        
        stats = cache.get_stats()
        assert stats["total_entries"] == 3
        
        assert cache.get({"key": "k0"}) is None
        assert cache.get({"key": "k1"}) is None
        assert cache.get({"key": "k2"}) is not None

    def test_lru_order_maintenance(self):
        """验证LRU访问顺序维护"""
        cache = EvaluationCache(max_size=3)
        
        cache.set({"key": "k1"}, {"value": 1})
        cache.set({"key": "k2"}, {"value": 2})
        cache.set({"key": "k3"}, {"value": 3})
        
        cache.get({"key": "k1"})
        
        cache.set({"key": "k4"}, {"value": 4})
        
        assert cache.get({"key": "k1"}) is not None
        assert cache.get({"key": "k2"}) is None

    def test_max_size_enforcement(self):
        """验证最大容量限制"""
        max_size = 5
        cache = EvaluationCache(max_size=max_size)
        
        for i in range(max_size + 5):
            cache.set({"key": f"k{i}"}, {"value": i})
        
        stats = cache.get_stats()
        assert stats["total_entries"] == max_size

    def test_invalidate(self):
        """验证失效操作"""
        cache = EvaluationCache(max_size=10)
        
        request_data = {"key": "test"}
        cache.set(request_data, {"value": 1})
        
        assert cache.get(request_data) is not None
        
        cache.invalidate(request_data)
        
        assert cache.get(request_data) is None

    def test_invalidate_with_str_key(self):
        """验证使用str key的失效操作"""
        cache = EvaluationCache(max_size=10)
        
        cache.set("test_key", {"value": 1})
        
        assert cache.get("test_key") is not None
        
        cache.invalidate("test_key")
        
        assert cache.get("test_key") is None

    def test_cache_stats(self):
        """验证缓存统计信息"""
        cache = EvaluationCache(max_size=10)
        
        request_data = {"key": "test"}
        cache.set(request_data, {"value": 1})
        
        cache.get(request_data)
        cache.get(request_data)
        
        stats = cache.get_stats()
        
        assert stats["total_entries"] == 1
        assert stats["total_hits"] == 2
        assert stats["hit_rate"] == 1.0

    def test_persistence_load(self):
        """验证持久化加载"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "evaluation_cache.json")
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump({
                    "key1": {"result": {"score": 0.85}},
                    "key2": {"result": {"score": 0.9}},
                }, f)
            
            cache = EvaluationCache(cache_dir=tmpdir, max_size=10)
            
            assert cache.get("key1") is not None
            assert cache.get("key2") is not None

    def test_persistence_empty_file(self):
        """验证空文件处理"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "evaluation_cache.json")
            with open(cache_file, "w", encoding="utf-8") as f:
                f.write("")
            
            cache = EvaluationCache(cache_dir=tmpdir, max_size=10)
            
            stats = cache.get_stats()
            assert stats["total_entries"] == 0

    def test_persistence_missing_file(self):
        """验证缺少文件时正常初始化"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = EvaluationCache(cache_dir=tmpdir, max_size=10)
            
            stats = cache.get_stats()
            assert stats["total_entries"] == 0

    def test_memory_leak_prevention(self):
        """验证内存泄漏预防（容量限制）"""
        cache = EvaluationCache(max_size=100)
        
        for i in range(1000):
            cache.set({"key": f"k{i}"}, {"value": i})
        
        stats = cache.get_stats()
        assert stats["total_entries"] == 100
        
        del cache

    def test_same_request_data_produces_same_key(self):
        """验证相同请求数据产生相同缓存key"""
        cache = EvaluationCache(max_size=10)
        
        request_data1 = {"question": "hello", "answer": "world"}
        request_data2 = {"question": "hello", "answer": "world"}
        
        cache.set(request_data1, {"score": 0.8})
        result = cache.get(request_data2)
        
        assert result is not None
        assert result["score"] == 0.8

    def test_different_request_data_produces_different_key(self):
        """验证不同请求数据产生不同缓存key"""
        cache = EvaluationCache(max_size=10)
        
        cache.set({"key": "a"}, {"value": 1})
        
        assert cache.get({"key": "b"}) is None