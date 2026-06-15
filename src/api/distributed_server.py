"""
增强的 API Server

集成:
- 限流
- 追踪
- 指标
- 熔断器
- 健康检查
"""

import logging
import os
import time
from contextlib import asynccontextmanager

import redis
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.distributed.rate_limiter import (
    MultiDimensionRateLimiter,
)
from src.infra.monitoring.metrics import expose_metrics
from src.infra.monitoring.metrics import registry as metrics_registry
from src.infra.monitoring.tracing import (
    SpanContextCarrier,
    TraceContext,
    get_tracer,
    setup_opentelemetry,
)
from src.workers.celery_app import celery_app
from src.workers.tasks import eval_case_task

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =====================================================================
# 1. 依赖注入
# =====================================================================

_redis_client: redis.Redis | None = None
_rate_limiter: MultiDimensionRateLimiter | None = None


def get_redis() -> redis.Redis:
    """获取 Redis 客户端"""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=int(os.getenv("REDIS_DB", "0")),
            decode_responses=True,
        )
    return _redis_client


def get_rate_limiter() -> MultiDimensionRateLimiter:
    """获取限流器"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = MultiDimensionRateLimiter(get_redis())
    return _rate_limiter


# =====================================================================
# 2. 追踪中间件
# =====================================================================


async def tracing_middleware(request: Request, call_next):
    """追踪中间件"""
    tracer = get_tracer()

    # 提取或创建 trace context
    headers = dict(request.headers)
    span_context = SpanContextCarrier.extract(headers)

    if span_context:
        pass
    else:
        pass

    # 创建 span
    with TraceContext(tracer, f"{request.method} {request.url.path}") as ctx:
        ctx.span.set_attribute("http.method", request.method)
        ctx.span.set_attribute("http.url", str(request.url))
        ctx.span.set_attribute("http.host", request.headers.get("host", ""))

        # 记录用户 IP
        client_ip = request.client.host if request.client else "unknown"
        ctx.span.set_attribute("client.ip", client_ip)

        try:
            response = await call_next(request)

            ctx.span.set_attribute("http.status_code", response.status_code)

            # 添加 trace ID 到响应头
            response.headers["X-Trace-ID"] = ctx.span.trace_id

            return response
        except Exception as e:
            ctx.span.set_status("ERROR", str(e))
            raise


# =====================================================================
# 3. 限流中间件
# =====================================================================


async def rate_limit_middleware(request: Request, call_next):
    """限流中间件"""
    rate_limiter = get_rate_limiter()

    # 提取限流维度
    user_id = request.headers.get("X-User-ID")
    api_key = request.headers.get("X-API-Key")
    client_ip = request.client.host if request.client else "unknown"

    # 检查限流
    is_allowed, result = rate_limiter.is_allowed(
        user_id=user_id,
        api_key=api_key,
        ip=client_ip,
    )

    if not is_allowed:
        logger.warning(f"Rate limit exceeded for {user_id or api_key or client_ip}")
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": "rate_limit_exceeded",
                "message": "Too many requests",
                "retry_after_ms": result.retry_after_ms,
            },
            headers={
                "Retry-After": str((result.retry_after_ms or 1000) // 1000),
                "X-RateLimit-Remaining": str(result.remaining_tokens if result else 0),
            },
        )

    response = await call_next(request)

    # 添加限流信息到响应头（result 可能为 None）
    if result:
        response.headers["X-RateLimit-Remaining"] = str(result.remaining_tokens)

    return response


# =====================================================================
# 4. 应用生命周期
# =====================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    # 启动
    logger.info("Starting AI Eval Platform API...")

    # 初始化追踪
    setup_opentelemetry(
        service_name="eval-platform-api",
        otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
    )

    # 初始化指标（metrics_registry 已在模块导入时初始化）
    logger.info("Metrics registry initialized")

    logger.info("AI Eval Platform API started")

    yield

    # 关闭
    logger.info("Shutting down AI Eval Platform API...")


# =====================================================================
# 5. FastAPI 应用
# =====================================================================

app = FastAPI(
    title="AI Eval Platform",
    description="分布式 AI 评测平台",
    version="2.0.0",
    lifespan=lifespan,
)

# 添加中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(tracing_middleware)
app.middleware("http")(rate_limit_middleware)


# =====================================================================
# 6. API 路由
# =====================================================================


@app.get("/health")
async def health_check():
    """健康检查 - 返回服务基本信息"""
    from src.config import settings

    return {
        "status": "healthy",
        "timestamp": time.time(),
        "service": settings.app_name,
        "version": settings.app_version,
    }


@app.get("/health/ready")
async def readiness_check():
    """
    Readiness 检查 - 检查所有依赖服务

    检查:
    - Redis 连接
    - 数据库连接
    - RabbitMQ 连接 (如果配置了)
    """
    from sqlalchemy import text

    from src.config import settings

    checks = {
        "redis": False,
        "database": False,
        "rabbitmq": False,
    }

    # 检查 Redis
    try:
        redis_client = get_redis()
        redis_client.ping()
        checks["redis"] = True
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")

    # 检查数据库
    try:
        from src.infra.db.session import engine

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")

    # 检查 RabbitMQ (如果 celery broker 已配置)
    if settings.celery_broker_url:
        try:
            import pika  # noqa: F401

            params = pika.URLParameters(settings.celery_broker_url)
            connection = pika.BlockingConnection(params)
            connection.close()
            checks["rabbitmq"] = True
        except Exception as e:
            logger.warning(f"RabbitMQ health check failed: {e}")
    else:
        # 如果没配置 Celery broker，标记为 N/A
        checks["rabbitmq"] = None

    # 判断是否就绪：Redis 和 Database 必须可用
    is_ready = checks["redis"] and checks["database"]

    return {
        "status": "ready" if is_ready else "not_ready",
        "checks": checks,
        "timestamp": time.time(),
    }


@app.get("/health/live")
async def liveness_check():
    """Liveness 检查 - 仅确认进程存活"""
    return {"status": "alive", "timestamp": time.time()}


@app.get("/health/detailed")
async def detailed_health():
    """
    详细健康检查 - 包含所有组件状态和配置信息

    用于运维监控和调试
    """
    from sqlalchemy import text

    from src.config import settings

    health_info = {
        "service": {
            "name": settings.app_name,
            "version": settings.app_version,
            "debug": settings.debug,
        },
        "components": {},
        "dependencies": {},
        "timestamp": time.time(),
    }

    # 检查各组件
    components = health_info["components"]

    # Redis
    try:
        redis_client = get_redis()
        redis_client.ping()
        info = redis_client.info()
        components["redis"] = {
            "status": "healthy",
            "version": info.get("redis_version", "unknown"),
            "connected_clients": info.get("connected_clients", 0),
        }
    except Exception as e:
        components["redis"] = {"status": "unhealthy", "error": str(e)}

    # 数据库
    try:
        from src.infra.db.session import engine

        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.scalar()
        db_url = settings.database_url
        components["database"] = {
            "status": "healthy",
            "url": db_url.split("@")[-1] if "@" in db_url else "embedded",
        }
    except Exception as e:
        components["database"] = {"status": "unhealthy", "error": str(e)}

    # RabbitMQ
    try:
        if settings.celery_broker_url:
            import pika

            params = pika.URLParameters(settings.celery_broker_url)
            connection = pika.BlockingConnection(params)
            connection.close()
            components["rabbitmq"] = {"status": "healthy"}
        else:
            components["rabbitmq"] = {"status": "not_configured"}
    except Exception as e:
        components["rabbitmq"] = {"status": "unhealthy", "error": str(e)}

    # 熔断器状态 (如果有的话)
    try:
        from src.distributed.circuit_breaker import CircuitBreakerRegistry

        registry = CircuitBreakerRegistry.get_instance()
        breakers = registry.list_breakers()
        components["circuit_breakers"] = {
            "count": len(breakers),
            "breakers": {name: cb.get_state() for name, cb in breakers.items()},
        }
    except Exception:
        components["circuit_breakers"] = {"status": "not_available"}

    return health_info


@app.get("/metrics")
async def metrics():
    """Prometheus 指标"""
    return Response(
        content=expose_metrics(),
        media_type="text/plain",
    )


@app.get("/metrics/json")
async def metrics_json():
    """JSON 格式的指标"""
    from prometheus_client import CollectorRegistry

    def _collect_metrics(registry: CollectorRegistry) -> list[dict]:
        """收集指标并转换为 JSON 格式"""
        metrics = []
        for collector in registry._collector_to_names.keys():
            for metric in collector.collect():
                metrics.append({
                    "name": metric.name,
                    "help": metric.documentation,
                    "type": metric.type,
                    "samples": [
                        {
                            "labels": dict(sample.labels),
                            "value": float(sample.value),
                            "timestamp": sample.timestamp,
                        }
                        for sample in metric.samples
                    ],
                })
        return metrics

    return _collect_metrics(metrics_registry)


@app.post("/api/v1/evaluate")
async def evaluate_sync(request: Request):
    """
    同步评测接口

    直接执行评测，返回结果
    """
    body = await request.json()

    tracer = get_tracer()
    with TraceContext(tracer, "api.evaluate_sync") as ctx:
        ctx.span.set_attribute("case_id", body.get("case_id", ""))
        ctx.span.set_attribute("domain", body.get("domain", ""))

        try:
            # 这里应该调用评测引擎
            # 简化实现
            return {
                "status": "success",
                "case_id": body.get("case_id"),
                "result": {
                    "score": 0.95,
                    "is_valid": True,
                },
                "trace_id": ctx.span.trace_id,
            }
        except Exception as e:
            ctx.span.set_status("ERROR", str(e))
            raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/v1/evaluate/async")
async def evaluate_async(request: Request, response: Response):
    """
    异步评测接口

    提交任务到队列，立即返回 task_id
    """
    body = await request.json()

    tracer = get_tracer()
    with TraceContext(tracer, "api.evaluate_async") as ctx:
        case_id = body.get("case_id", f"case_{int(time.time())}")
        ctx.span.set_attribute("case_id", case_id)
        ctx.span.set_attribute("domain", body.get("domain", ""))

        try:
            # 提交 Celery 任务
            task = eval_case_task.delay(body)

            response.headers["X-Trace-ID"] = ctx.span.trace_id
            response.headers["X-Task-ID"] = task.id

            return {
                "status": "queued",
                "task_id": task.id,
                "case_id": case_id,
            }
        except Exception as e:
            ctx.span.set_status("ERROR", str(e))
            raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/v1/tasks/{task_id}")
async def get_task_status(task_id: str):
    """查询任务状态"""
    result = celery_app.AsyncResult(task_id)

    return {
        "task_id": task_id,
        "state": result.state,
        "result": result.result if result.ready() else None,
    }


@app.get("/api/v1/tasks/{task_id}/result")
async def get_task_result(task_id: str):
    """获取任务结果"""
    result = celery_app.AsyncResult(task_id)

    if not result.ready():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not ready",
        )

    return result.result


# =====================================================================
# 7. 启动
# =====================================================================

if __name__ == "__main__":
    import os

    import uvicorn

    host = os.environ.get("API_HOST", "127.0.0.1")
    port = int(os.environ.get("API_PORT", "8000"))

    uvicorn.run(
        "src.api.server:app",
        host=host,
        port=port,
        reload=True,
        log_level="info",
    )
