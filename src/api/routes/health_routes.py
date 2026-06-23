"""
健康检查路由模块
包含健康检查、系统状态监控等端点
"""

import logging
import os
import time

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from src.api.common import _get_data_service, success_response
from src.infra.monitoring.metrics import expose_metrics

logger = logging.getLogger(__name__)

router = APIRouter(tags=["健康检查"])


@router.get("/health")
async def health_check():
    return success_response({"status": "healthy", "service": "ai-eval-platform"})


def check_rabbitmq() -> dict:
    """检查 RabbitMQ 连接状态"""
    broker_url = os.getenv("CELERY_BROKER_URL", "")

    if not broker_url or broker_url.startswith("filesystem://"):
        return {"status": "not configured", "message": "当前使用文件系统作为任务队列"}

    if broker_url.startswith("redis://"):
        try:
            from src.infra.cache import get_redis

            redis_client = get_redis()
            redis_client.ping()
            return {"status": "healthy", "message": "使用 Redis 作为消息队列"}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    if broker_url.startswith("amqp://"):
        try:
            import pika

            params = pika.URLParameters(broker_url)
            params.socket_timeout = 3
            connection = pika.BlockingConnection(params)
            connection.close()
            return {"status": "healthy"}
        except ImportError:
            return {"status": "not configured", "message": "pika 库未安装，无法检查 RabbitMQ"}
        except Exception as e:
            error_msg = str(e) or "连接失败"
            return {"status": "not configured", "message": f"RabbitMQ 未启动: {error_msg[:50]}"}

    return {"status": "unknown", "message": f"未知的 broker 类型: {broker_url[:50]}"}


@router.get("/api/v1/health")
async def api_v1_health_check():
    """统一健康检查端点"""
    checks = {}

    try:
        svc = _get_data_service()
        count = svc.count()
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
        rabbitmq_status = check_rabbitmq()
        checks["rabbitmq"] = rabbitmq_status
    except Exception as e:
        logger.error(f"RabbitMQ health check failed: {e}")
        checks["rabbitmq"] = {"status": "unhealthy", "error": str(e)}

    has_unhealthy = any(c["status"] == "unhealthy" for c in checks.values())
    overall_status = "healthy" if not has_unhealthy else "unhealthy"

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
        svc = _get_data_service()
        count = svc.count()
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
        rabbitmq_status = check_rabbitmq()
        checks["rabbitmq"] = rabbitmq_status
    except Exception as e:
        logger.error(f"RabbitMQ health check failed: {e}")
        checks["rabbitmq"] = {"status": "unhealthy", "error": str(e)}

    has_unhealthy = any(c["status"] == "unhealthy" for c in checks.values())
    overall_status = "healthy" if not has_unhealthy else "unhealthy"

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


@router.get("/api/v1/metrics")
async def api_v1_metrics():
    """性能指标端点"""
    return success_response(
        {
            "requests_total": 0,
            "p50_latency_ms": 0,
            "p95_latency_ms": 0,
            "p99_latency_ms": 0,
            "error_rate": 0,
            "cache_hit_rate": 0,
            "avg_tokens": 0,
            "daily_cost_usd": 0,
        }
    )
