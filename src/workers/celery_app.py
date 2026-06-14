import redis  # noqa: F401

# celery -A src.workers.celery_app worker --loglevel=info

# =====================================================================
# 1. 物理层底层协议与特性拦截补丁 (Ultimate Redis 5 Engine Patch)
# =====================================================================
original_init = redis.Connection.__init__


def safe_connection_init(self, *args, **kwargs):
    # A. 强制锁死 RESP2 协议以兼容物理 Redis 5.0.14 数据库
    kwargs["protocol"] = 2

    # B. 强行关闭新版驱动在老版本协议下会报错的云维护通知特性
    # 直接清空相关字典，防止其进入底层执行 _configure_maintenance_notifications
