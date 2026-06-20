import hashlib
import json
import os
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class CacheEntry:
    key: str
    result: dict[str, Any]
    created_at: datetime = field(default_factory=datetime.utcnow)
    hit_count: int = 0
    avg_latency_ms: float = 0.0


class EvaluationCache:
    def __init__(self, cache_dir: str = "data/cache", ttl_seconds: int = 3600):
        self._cache: dict[str, CacheEntry] = {}
        self._cache_dir = cache_dir
        self._ttl_seconds = ttl_seconds
        self._load_cache()

    def _load_cache(self):
        cache_file = os.path.join(self._cache_dir, "evaluation_cache.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, encoding="utf-8") as f:
                    data = json.load(f)
                    for key, entry in data.items():
                        entry_obj = CacheEntry(
                            key=key,
                            result=entry["result"],
                            created_at=datetime.fromisoformat(entry["created_at"]),
                            hit_count=entry.get("hit_count", 0),
                            avg_latency_ms=entry.get("avg_latency_ms", 0.0)
                        )
                        if not self._is_expired(entry_obj):
                            self._cache[key] = entry_obj
            except Exception:
                pass

    def _save_cache(self):
        cache_file = os.path.join(self._cache_dir, "evaluation_cache.json")
        os.makedirs(self._cache_dir, exist_ok=True)
        data = {
            key: {
                "result": entry.result,
                "created_at": entry.created_at.isoformat(),
                "hit_count": entry.hit_count,
                "avg_latency_ms": entry.avg_latency_ms
            }
            for key, entry in self._cache.items()
        }
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _is_expired(self, entry: CacheEntry) -> bool:
        age = (datetime.utcnow() - entry.created_at).total_seconds()
        return age > self._ttl_seconds

    def _generate_key(self, request_data: dict[str, Any]) -> str:
        content = json.dumps(request_data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def get(self, request_data: dict[str, Any]) -> dict[str, Any] | None:
        key = self._generate_key(request_data)
        entry = self._cache.get(key)

        if entry and not self._is_expired(entry):
            entry.hit_count += 1
            self._save_cache()
            return entry.result

        return None

    def set(self, request_data: dict[str, Any], result: dict[str, Any], latency_ms: float = 0.0):
        key = self._generate_key(request_data)
        entry = CacheEntry(
            key=key,
            result=result,
            avg_latency_ms=latency_ms
        )
        self._cache[key] = entry
        self._save_cache()

    def invalidate(self, request_data: dict[str, Any]):
        key = self._generate_key(request_data)
        if key in self._cache:
            del self._cache[key]
            self._save_cache()

    def clear(self):
        self._cache.clear()
        self._save_cache()

    def get_stats(self) -> dict[str, Any]:
        total_hits = sum(e.hit_count for e in self._cache.values())
        total_entries = len(self._cache)
        avg_latency = sum(e.avg_latency_ms for e in self._cache.values()) / max(total_entries, 1)

        return {
            "total_entries": total_entries,
            "total_hits": total_hits,
            "hit_rate": total_hits / max(total_entries, 1),
            "avg_latency_ms": round(avg_latency, 2),
            "cache_size_kb": self._get_cache_size(),
        }

    def _get_cache_size(self) -> float:
        cache_file = os.path.join(self._cache_dir, "evaluation_cache.json")
        if os.path.exists(cache_file):
            return os.path.getsize(cache_file) / 1024
        return 0.0


class AsyncEvaluationProcessor:
    def __init__(self, max_workers: int = 4):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._pending_tasks: dict[str, Any] = {}

    def submit(self, task_id: str, func: Callable, *args, **kwargs) -> Any:
        future = self._executor.submit(func, *args, **kwargs)
        self._pending_tasks[task_id] = {
            "future": future,
            "submitted_at": datetime.utcnow(),
            "status": "running"
        }
        return future

    def get_result(self, task_id: str, timeout: float = None) -> Any | None:
        task = self._pending_tasks.get(task_id)
        if not task:
            return None

        future = task["future"]
        if future.done():
            task["status"] = "completed"
            task["completed_at"] = datetime.utcnow()
            return future.result(timeout=timeout)

        return None

    def get_task_status(self, task_id: str) -> str:
        task = self._pending_tasks.get(task_id)
        if not task:
            return "not_found"

        future = task["future"]
        if future.done():
            return "completed"
        elif future.cancelled():
            return "cancelled"
        else:
            return "running"

    def cancel_task(self, task_id: str) -> bool:
        task = self._pending_tasks.get(task_id)
        if task:
            cancelled = task["future"].cancel()
            if cancelled:
                task["status"] = "cancelled"
            return cancelled
        return False

    def cleanup_completed(self):
        self._pending_tasks = {
            k: v for k, v in self._pending_tasks.items()
            if v["status"] == "running"
        }


class PerformanceOptimizer:
    def __init__(self):
        self._cache = EvaluationCache()
        self._async_processor = AsyncEvaluationProcessor(max_workers=4)
        self._metrics: list[dict[str, Any]] = []
        self._max_metrics = 1000

    def cached_evaluate(self, request_data: dict[str, Any], evaluate_func: Callable) -> dict[str, Any]:
        cached_result = self._cache.get(request_data)
        if cached_result:
            return {
                **cached_result,
                "from_cache": True,
                "latency_ms": 0
            }

        start_time = time.time()
        result = evaluate_func(request_data)
        latency_ms = (time.time() - start_time) * 1000

        result["from_cache"] = False
        result["latency_ms"] = latency_ms

        self._cache.set(request_data, result, latency_ms)
        self._record_metric(latency_ms, result.get("from_cache", False))

        return result

    def async_batch_evaluate(self, requests: list[dict[str, Any]], evaluate_func: Callable) -> list[dict[str, Any]]:
        results = []

        futures = {}
        for i, req in enumerate(requests):
            task_id = f"eval_{i}_{int(time.time())}"
            future = self._async_processor.submit(task_id, evaluate_func, req)
            futures[task_id] = (i, future)

        for idx, future in futures.values():
            try:
                result = future.result(timeout=30)
                results.append((idx, result))
            except Exception as e:
                results.append((idx, {"error": str(e)}))

        results.sort(key=lambda x: x[0])
        return [r[1] for r in results]

    def _record_metric(self, latency_ms: float, from_cache: bool):
        metric = {
            "timestamp": datetime.utcnow().isoformat(),
            "latency_ms": latency_ms,
            "from_cache": from_cache
        }
        self._metrics.append(metric)
        if len(self._metrics) > self._max_metrics:
            self._metrics = self._metrics[-self._max_metrics:]

    def get_performance_report(self) -> dict[str, Any]:
        if not self._metrics:
            return {
                "total_requests": 0,
                "avg_latency_ms": 0,
                "p50_latency_ms": 0,
                "p95_latency_ms": 0,
                "p99_latency_ms": 0,
                "cache_hit_rate": 0,
                "recommendations": ["暂无数据"]
            }

        non_cached = [m for m in self._metrics if not m["from_cache"]]
        latencies = sorted([m["latency_ms"] for m in non_cached])

        total = len(self._metrics)
        cache_hits = sum(1 for m in self._metrics if m["from_cache"])

        p50_idx = int(len(latencies) * 0.5)
        p95_idx = int(len(latencies) * 0.95)
        p99_idx = int(len(latencies) * 0.99)

        recommendations = []
        avg_latency = sum(latencies) / max(len(latencies), 1)
        if avg_latency > 2000:
            recommendations.append("P0: 平均延迟超过2秒，建议启用缓存或降级到本地模型")
        if cache_hits / total < 0.3:
            recommendations.append("缓存命中率过低，考虑增加缓存TTL或优化缓存策略")

        return {
            "total_requests": total,
            "avg_latency_ms": round(avg_latency, 2),
            "p50_latency_ms": round(latencies[p50_idx] if latencies else 0, 2),
            "p95_latency_ms": round(latencies[p95_idx] if latencies else 0, 2),
            "p99_latency_ms": round(latencies[p99_idx] if latencies else 0, 2),
            "cache_hit_rate": round(cache_hits / total, 3),
            "recommendations": recommendations if recommendations else ["性能表现良好"]
        }


evaluation_cache = EvaluationCache()
performance_optimizer = PerformanceOptimizer()
