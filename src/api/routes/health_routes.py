"""
健康检查路由模块
包含健康检查、系统状态监控等端点
"""

import logging
import time

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from src.api.common import _get_celery_app, _get_repository, success_response
from src.infra.monitoring.metrics import expose_metrics

logger = logging.getLogger(__name__)

router = APIRouter(tags=["健康检查"])


@router.get("/health")
async def health_check():
    return success_response({"status": "healthy", "service": "ai-eval-platform"})


@router.get("/api/v1/health")
async def api_v1_health_check():
    """统一健康检查端点"""
    checks = {}

    try:
        repo = _get_repository()
        count = repo.count()
        checks["database"] = {"status": "healthy", "record_count": count}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        checks["database"] = {"status": "unhealthy", "error": "数据库连接失败"}

    try:
        from src.infra.cache import get_redis

        redis_client = get_redis()
        redis_client.ping()
        checks["redis"] = {"status": "healthy"}
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        checks["redis"] = {"status": "unhealthy", "error": "缓存连接失败"}

    try:
        _get_celery_app()
        checks["celery"] = {"status": "healthy"}
    except Exception as e:
        logger.error(f"Celery health check failed: {e}")
        checks["celery"] = {"status": "unhealthy", "error": "任务队列连接失败"}

    overall_status = (
        "healthy" if all(c["status"] == "healthy" for c in checks.values()) else "unhealthy"
    )

    return success_response(
        {
            "status": overall_status,
            "service": "ai-eval-platform",
            "components": checks,
        }
    )


@router.get("/api/v1/health/detailed")
async def api_v1_health_detailed():
    """详细健康检查端点"""
    checks = {}

    try:
        repo = _get_repository()
        count = repo.count()
        checks["database"] = {"status": "healthy", "record_count": count}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        checks["database"] = {"status": "unhealthy", "error": str(e)}

    try:
        from src.infra.cache import get_redis

        redis_client = get_redis()
        redis_client.ping()
        checks["redis"] = {"status": "healthy"}
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        checks["redis"] = {"status": "unhealthy", "error": str(e)}

    try:
        _get_celery_app()
        checks["celery"] = {"status": "healthy"}
    except Exception as e:
        logger.error(f"Celery health check failed: {e}")
        checks["celery"] = {"status": "unhealthy", "error": str(e)}

    overall_status = (
        "healthy" if all(c["status"] == "healthy" for c in checks.values()) else "unhealthy"
    )

    return success_response(
        {
            "service": {
                "name": "ai-eval-platform",
                "version": "2.0.0",
                "timestamp": int(time.time()),
            },
            "status": overall_status,
            "components": checks,
            "metrics": {
                "requests_total": 0,
                "avg_latency_ms": 0,
                "error_rate": 0,
                "cache_hit_rate": 0,
            },
        }
    )


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    return expose_metrics()
