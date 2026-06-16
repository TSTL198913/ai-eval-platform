import os

from celery import Celery

if os.getenv("TESTING") != "1":
    import redis

    original_init = redis.Connection.__init__

    def safe_connection_init(self, *args, **kwargs):
        kwargs["protocol"] = 2

        if "redis_services_context" in kwargs:
            kwargs["redis_services_context"] = None

        original_init(self, *args, **kwargs)

    redis.Connection._configure_maintenance_notifications = lambda *args, **kwargs: None
    redis.Connection.__init__ = safe_connection_init


# =====================================================================
# 2. 纯净实例化 (Celery Infrastructure)
# =====================================================================
BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
BACKEND_URL = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

celery_app = Celery(
    "eval_platform",
    broker=BROKER_URL,
    backend=BACKEND_URL,
    include=["src.workers.tasks"],
)

# 集中注入高可用核心参数
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_time_limit=60,  # 60秒强制超时熔断
    worker_max_tasks_per_child=50,  # 每个子进程执行50次任务自动重建，防内存泄漏
    task_ignore_result=False,  # 记录结果，确保 task.get() 顺畅无阻
    # 配置层对接
    broker_transport_options={"protocol": 2},
    result_backend_transport_options={"protocol": 2},
)

if __name__ == "__main__":
    celery_app.start()
