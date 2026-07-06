"""
缓存基础设施模块
"""

import sys
from importlib import import_module

from .redis_cluster_manager import RedisClusterManager, redis_cluster_manager


_cache_py_module = None
try:
    _cache_py_module = import_module('src.infra.cache_impl')
except ImportError:
    pass


if _cache_py_module is not None:
    get_redis_client = getattr(_cache_py_module, 'get_redis_client', lambda: redis_cluster_manager.get_client())
    get_redis = getattr(_cache_py_module, 'get_redis', lambda: redis_cluster_manager.get_client())
    EvaluationCache = getattr(_cache_py_module, 'EvaluationCache', None)
    cached = getattr(_cache_py_module, 'cached', None)
    _cache = getattr(_cache_py_module, '_cache', None)
else:
    def get_redis_client():
        return redis_cluster_manager.get_client()

    def get_redis():
        return redis_cluster_manager.get_client()

    EvaluationCache = None
    cached = None
    _cache = None


__all__ = [
    "RedisClusterManager",
    "redis_cluster_manager",
    "get_redis_client",
    "get_redis",
    "EvaluationCache",
    "cached",
    "_cache",
]