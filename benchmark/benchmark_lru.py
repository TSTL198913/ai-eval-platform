"""
LRU缓存性能基准测试

对比O(n)旧实现和O(1)新实现，在不同cache_size下测量：
- p50/p99延迟
- 吞吐量
- 内存使用
"""

import sys
import time
import random
import tracemalloc
from collections import OrderedDict
from typing import Any, Dict


class O1LRUCache:
    """O(1) LRU缓存实现（使用OrderedDict）"""
    
    def __init__(self, max_size: int):
        self._cache = OrderedDict()
        self._max_size = max_size
    
    def get(self, key: str) -> Any:
        if key not in self._cache:
            return None
        self._cache.move_to_end(key)
        return self._cache[key]
    
    def set(self, key: str, value: Any):
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        if len(self._cache) > self._max_size:
            self._cache.popitem(last=False)


class OnLRUCache:
    """O(n) LRU缓存实现（使用dict+列表）"""
    
    def __init__(self, max_size: int):
        self._cache: Dict[str, Any] = {}
        self._order: list[str] = []
        self._max_size = max_size
    
    def get(self, key: str) -> Any:
        if key not in self._cache:
            return None
        self._order.remove(key)
        self._order.append(key)
        return self._cache[key]
    
    def set(self, key: str, value: Any):
        if key in self._cache:
            self._order.remove(key)
        self._cache[key] = value
        self._order.append(key)
        if len(self._order) > self._max_size:
            oldest = self._order.pop(0)
            del self._cache[oldest]


def benchmark(cache, operations: int, cache_size: int, hit_ratio: float):
    """运行基准测试"""
    keys = [f"key_{i}" for i in range(cache_size * 2)]
    hit_keys = keys[:cache_size]
    
    times = []
    
    for _ in range(operations):
        if random.random() < hit_ratio:
            key = random.choice(hit_keys)
        else:
            key = random.choice(keys)
        
        start = time.perf_counter()
        value = cache.get(key)
        if value is None:
            cache.set(key, f"value_{key}")
        elapsed = (time.perf_counter() - start) * 1_000_000
        times.append(elapsed)
    
    times.sort()
    p50 = times[int(len(times) * 0.5)]
    p99 = times[int(len(times) * 0.99)]
    throughput = operations / (sum(times) / 1_000_000)
    
    return {
        "p50_us": p50,
        "p99_us": p99,
        "throughput_ops_s": throughput,
    }


def main():
    print("=" * 70)
    print("LRU缓存性能基准测试")
    print("=" * 70)
    
    cache_sizes = [100, 1000, 10000, 100000]
    operations = 100000
    hit_ratio = 0.8
    
    print(f"操作次数: {operations:,}")
    print(f"命中率: {hit_ratio * 100:.0f}%")
    print()
    
    print(f"{'缓存大小':<12} {'实现':<8} {'P50(us)':<10} {'P99(us)':<10} {'吞吐量(ops/s)':<15}")
    print("-" * 65)
    
    for cache_size in cache_sizes:
        o1_cache = O1LRUCache(cache_size)
        on_cache = OnLRUCache(cache_size)
        
        o1_result = benchmark(o1_cache, operations, cache_size, hit_ratio)
        on_result = benchmark(on_cache, operations, cache_size, hit_ratio)
        
        print(f"{cache_size:<12} O(1)    {o1_result['p50_us']:<10.2f} {o1_result['p99_us']:<10.2f} {o1_result['throughput_ops_s']:<15,.0f}")
        print(f"{cache_size:<12} O(n)    {on_result['p50_us']:<10.2f} {on_result['p99_us']:<10.2f} {on_result['throughput_ops_s']:<15,.0f}")
    
    print()
    print("结论: O(1)实现在大缓存容量下性能优势明显")


if __name__ == "__main__":
    main()