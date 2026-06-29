import os
import tempfile

from celery import Celery

# celery -A src.workers.celery_app worker --loglevel=info

# 使用文件系统作为broker，避免依赖Redis
BROKER_URL = os.getenv("CELERY_BROKER_URL", f"filesystem://{tempfile.gettempdir()}/celery_broker")
BACKEND_URL = os.getenv(
    "CELERY_RESULT_BACKEND", f"filesystem://{tempfile.gettempdir()}/celery_backend"
)

# 任务并发数配置
WORKER_CONCURRENCY = int(os.getenv("CELERY_WORKER_CONCURRENCY", "4"))
WORKER_PREFETCH_MULTIPLIER = int(os.getenv("CELERY_WORKER_PREFETCH_MULTIPLIER", "1"))

# 任务超时配置（修复：soft_time_limit 必须小于 time_limit）
TASK_SOFT_TIME_LIMIT = int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT", "45"))
TASK_TIME_LIMIT = int(os.getenv("CELERY_TASK_TIME_LIMIT", "60"))

# 启动时验证配置正确性
if TASK_SOFT_TIME_LIMIT >= TASK_TIME_LIMIT:
    raise ValueError(
        f"Celery配置错误：soft_time_limit({TASK_SOFT_TIME_LIMIT}) 必须 < time_limit({TASK_TIME_LIMIT})"
    )

# 任务重试策略配置
TASK_MAX_RETRIES = int(os.getenv("CELERY_TASK_MAX_RETRIES", "3"))
TASK_RETRY_BACKOFF = bool(os.getenv("CELERY_TASK_RETRY_BACKOFF", "true").lower() == "true")
TASK_RETRY_BACKOFF_MAX = int(os.getenv("CELERY_TASK_RETRY_BACKOFF_MAX", "600"))
TASK_RETRY_JITTER = bool(os.getenv("CELERY_TASK_RETRY_JITTER", "true").lower() == "true")

# 任务缓冲配置
TASK_ACKS_LATE = bool(os.getenv("CELERY_TASK_ACKS_LATE", "true").lower() == "true")
TASK_REJECT_ON_WORKER_LOST = bool(
    os.getenv("CELERY_TASK_REJECT_ON_WORKER_LOST", "true").lower() == "true"
)

# Worker配置
WORKER_MAX_TASKS_PER_CHILD = int(os.getenv("CELERY_WORKER_MAX_TASKS_PER_CHILD", "50"))
WORKER_MAX_MEMORY_PER_CHILD = int(os.getenv("CELERY_WORKER_MAX_MEMORY_PER_CHILD", "524288"))  # KB

_celery_app = None


def get_celery_app() -> Celery:
    """延迟获取Celery应用实例"""
    global _celery_app
    if _celery_app is None:
        # 使用broker_transport_options配置RESP2协议，而非全局补丁
        _celery_app = Celery(
            "eval_platform",
            broker=BROKER_URL,
            backend=BACKEND_URL,
            include=["src.workers.tasks"],
        )

        _celery_app.conf.update(
            # 序列化配置
            task_serializer="json",
            accept_content=["json"],
            result_serializer="json",
            task_ignore_result=False,
            # 通过配置而非猴子补丁解决RESP2协议兼容问题
            broker_transport_options={"protocol": 2, "visibility_timeout": 3600},
            result_backend_transport_options={"protocol": 2},
            # 任务超时配置
            task_time_limit=TASK_TIME_LIMIT,
            task_soft_time_limit=TASK_SOFT_TIME_LIMIT,
            # 任务重试策略配置
            task_acks_late=TASK_ACKS_LATE,
            task_reject_on_worker_lost=TASK_REJECT_ON_WORKER_LOST,
            # Worker配置
            worker_max_tasks_per_child=WORKER_MAX_TASKS_PER_CHILD,
            worker_max_memory_per_child=WORKER_MAX_MEMORY_PER_CHILD,
            # 任务缓冲优化：预取倍数
            worker_prefetch_multiplier=WORKER_PREFETCH_MULTIPLIER,
            # 兼容性保留
            task_default_retry_delay=3,
        )
    return _celery_app


# 仅在非测试环境自动初始化
IS_TESTING = os.environ.get("TESTING", "0") == "1"
if not IS_TESTING:
    celery_app = get_celery_app()
else:
    celery_app = None


if __name__ == "__main__":
    get_celery_app().start()
