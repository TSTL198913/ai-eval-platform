import sys

from loguru import logger

from .tracing import trace_id_var

# 移除默认 handler
logger.remove()

# 添加配置，注入 trace_id
logger.add(
    sys.stderr,
    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{extra[trace_id]}</cyan> | "
        "<level>{message}</level>"
    ),
    level="INFO",
)

# 核心：定义 patch 函数，自动关联 contextvars
logger = logger.patch(
    lambda record: record["extra"].update(trace_id=trace_id_var.get())
)
