import logging
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
logger = logger.patch(lambda record: record["extra"].update(trace_id=trace_id_var.get()))

# 配置标准 logging 输出到 loguru，实现双框架兼容
class LoguruHandler(logging.Handler):
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

# 将标准 logging 的 root handler 替换为 loguru handler
logging.basicConfig(handlers=[LoguruHandler()], level=logging.INFO)
