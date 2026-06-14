"""
增强的 Celery Worker 配置

集成:
- Redis 连接池
- 分布式锁
- 熔断器
- 指标采集
- 追踪
"""

import logging
import os
import uuid

import redis
from celery import Celery, Task
from celery.signals import worker_init, worker_shutdown, task_prerun, task_postrun

from src.distributed.circuit_breaker import global_registry
from src.metrics import get_registry
from src.tracing import get_tracer

logger = logging.getLogger(__name__)

# =====================================================================
# 1. Redis 连接配置
# =====================================================================
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

# 统一 Redis 连接池
_redis_pool = redis.ConnectionPool(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    password=REDIS_PASSWORD,
    decode_responses=True,
    max_connections=50,
)


def get_redis_client() -> redis.Redis:
    """获取 Redis 客户端 (使用连接池)"""
    return redis.Redis(connection_pool=_redis_pool)


# =====================================================================
# 2. Celery 应用配置
# =====================================================================
BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
BACKEND_URL = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

celery_app = Celery(
    "eval_platform",
    broker=BROKER_URL,
    backend=BACKEND_URL,
    include=["src.worker.tasks"],
)

# Celery 配置
celery_app.conf.update(
    # 序列化
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # 任务执行配置
    task_acks_late=True,           # 任务完成后才 ACK，防止中途失败丢失
    task_reject_on_worker_lost=True,  # Worker 丢失时重新入队
    task_time_limit=120,           # 硬限制 120 秒
    task_soft_time_limit=90,       # 软限制 90 秒

    # Worker 配置
    worker_prefetch_multiplier=4,  # 预取任务数
    worker_max_tasks_per_child=100,  # 每个子进程最多执行 100 个任务，防止内存泄漏
    worker_disable_rate_limits=False,

    # 结果配置
    result_expires=3600,           # 结果过期时间 1 小时
    result_extended=True,          # 返回更多信息

    # 路由配置
    task_routes={
        "src.worker.tasks.eval_case_task": {"queue": "eval_tasks"},
        "src.worker.tasks.eval_case_task_high_prio": {"queue": "eval_tasks_high"},
    },

    # 定期任务
    beat_schedule={
        "flush-buffer-every-30s": {
            "task": "src.worker.tasks.flush_buffer",
            "schedule": 30.0,
        },
    },
)


# =====================================================================
# 3. Worker 生命周期钩子
# =====================================================================

@worker_init.connect
def on_worker_init(**kwargs):
    """Worker 初始化"""
    logger.info("=" * 50)
    logger.info("Worker initializing...")
    logger.info(f"Worker ID: {os.getenv('CELERY_WORKER_ID', 'unknown')}")
    logger.info(f"Redis: {REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")
    logger.info("=" * 50)


@worker_shutdown.connect
def on_worker_shutdown(**kwargs):
    """Worker 关闭"""
    logger.info("Worker shutting down...")
    # 刷新缓冲区
    try:
        from src.worker.tasks import get_buffer_service
        buffer_svc = get_buffer_service()
        if buffer_svc:
            buffer_svc.flush()
            logger.info("Buffer flushed successfully")
    except Exception as e:
        logger.error(f"Failed to flush buffer on shutdown: {e}")


# =====================================================================
# 4. 任务预绑定 (Task Binding)
# =====================================================================

class EvalTask(Task):
    """评测任务基类"""

    _redis_client = None
    _worker_id = None

    @property
    def redis(self) -> redis.Redis:
        """获取 Redis 客户端 (每 worker 一个)"""
        if self._redis_client is None:
            self._redis_client = get_redis_client()
        return self._redis_client

    @property
    def worker_id(self) -> str:
        """获取 Worker ID"""
        if self._worker_id is None:
            self._worker_id = os.getenv("CELERY_WORKER_ID", str(uuid.uuid4())[:8])
        return self._worker_id

    def before_start(self, task_id, args, kwargs):
        """任务开始前"""
        logger.debug(f"Task {task_id} starting on worker {self.worker_id}")

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        """任务返回后"""
        # 记录指标
        try:
            metrics = get_registry()
            counter = metrics.get_metric("celery_tasks_total")
            if counter:
                counter.inc(status=status.value)
        except Exception:
            pass

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """任务失败"""
        logger.error(f"Task {task_id} failed: {exc}")

        # 更新熔断器
        try:
            cb = global_registry.get_or_create(f"task_{kwargs.get('domain', 'unknown')}")
            cb._record_failure()
        except Exception:
            pass

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """任务重试"""
        logger.warning(f"Task {task_id} retrying: {exc}")

    def on_success(self, retval, task_id, args, kwargs):
        """任务成功"""
        logger.debug(f"Task {task_id} succeeded")


# =====================================================================
# 5. 追踪集成
# =====================================================================

@task_prerun.connect
def on_task_prerun(task_id, task, *args, **kwargs):
    """任务预执行"""
    tracer = get_tracer()
    span = tracer.create_span(
        f"celery.{task.name}",
        attributes={
            "task_id": task_id,
            "task_name": task.name,
        },
    )
    # 将 trace_id 存储在当前 context
    task._current_span = span


@task_postrun.connect
def on_task_postrun(task_id, task, *args, **kwargs):
    """任务后执行"""
    if hasattr(task, "_current_span"):
        span = task._current_span
        span.finish()
        tracer = get_tracer()
        tracer.end_span(span)
        del task._current_span
