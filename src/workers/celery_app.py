import os

import redis
from celery import Celery

#python -c "import sys; sys.path.insert(0, 'D:/workspace/ai-eval-platform-refactor'); from src.workers.celery_app import celery_app;
# celery_app.start(['worker', '--loglevel=warning', '-P', 'gevent', '--concurrency=2000'])"

# =====================================================================
# 1. 物理层底层协议与特性拦截补丁 (Ultimate Redis 5 Engine Patch)
# =====================================================================
original_init = redis.Connection.__init__


def safe_connection_init(self, *args, **kwargs):
    # 🎯 A. 强制锁死 RESP2 协议以兼容物理 Redis 5.0.14 数据库
    kwargs["protocol"] = 2

    # 🎯 B. 强行关闭新版驱动在老版本协议下会报错的“云维护通知”特性
    # 直接清空相关字典，防止其进入底层执行 _configure_maintenance_notifications
    if "redis_services_context" in kwargs:
        kwargs["redis_services_context"] = None

    original_init(self, *args, **kwargs)


# 🎯 C. 降维打击：直接空置新版驱动的维护通知配置函数，让它安全通过初始化
redis.Connection._configure_maintenance_notifications = lambda *args, **kwargs: None
# 注入我们的安全核心构造函数
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
    worker_max_tasks_per_child=50,  # 每个子进程执行 50 次任务自动重建，防内存泄漏
    task_ignore_result=False,  # 记录结果，确保 task.get() 畅通无阻
    # 配置层对齐
    broker_transport_options={"protocol": 2},
    result_backend_transport_options={"protocol": 2},
)

if __name__ == "__main__":
    celery_app.start()
