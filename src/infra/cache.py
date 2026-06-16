from collections.abc import Callable
from functools import wraps
from typing import Any

from src.infra.db.session import get_db_session


class EvaluationCache:
    def __init__(self, ttl_seconds: int = 60):
        self._cache: dict[str, tuple[Any, float]] = {}
        self._ttl = ttl_seconds

    def get(self, key: str) -> Any | None:
        import time

        item = self._cache.get(key)
        if item:
            value, timestamp = item
            if time.time() - timestamp < self._ttl:
                return value
            else:
                del self._cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        import time

        self._cache[key] = (value, time.time())

    def invalidate(self, key: str) -> None:
        self._cache.pop(key, None)

    def clear(self) -> None:
        self._cache.clear()


_cache = EvaluationCache()


def cached(key_prefix: str = "") -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = f"{key_prefix}:{args}:{kwargs}"
            cached_result = _cache.get(key)
            if cached_result is not None:
                return cached_result
            result = func(*args, **kwargs)
            _cache.set(key, result)
            return result

        return wrapper

    return decorator


def batch_insert(results: list[dict]) -> int:
    """批量插入评估结果"""
    if not results:
        return 0

    with get_db_session() as session:
        from src.infra.db.models import EvaluationResultModel

        db_records = [
            EvaluationResultModel(
                case_id=r.get("case_id"),
                model_name=r.get("model_name", "unknown"),
                adapter_name=r.get("adapter_name", "unknown"),
                status=r.get("status"),
                latency_ms=r.get("latency_ms", 0.0),
                response_data=r.get("response_data", {}),
            )
            for r in results
        ]
        session.add_all(db_records)
        session.commit()
        return len(db_records)
