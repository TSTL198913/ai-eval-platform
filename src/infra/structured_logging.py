# =====================================================================
# AI Evaluation Platform - 结构化日志系统
# =====================================================================

import json
import logging
import sys
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

# =====================================================================
# Context Variables - 用于跨函数传递追踪信息
# =====================================================================

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
span_id_var: ContextVar[str] = ContextVar("span_id", default="")
user_id_var: ContextVar[str] = ContextVar("user_id", default="")
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def get_trace_id() -> str:
    """获取当前 trace_id"""
    return trace_id_var.get()


def get_span_id() -> str:
    """获取当前 span_id"""
    return span_id_var.get()


def set_trace_context(trace_id: str, span_id: str = "") -> None:
    """设置追踪上下文"""
    trace_id_var.set(trace_id)
    if span_id:
        span_id_var.set(span_id)


def set_user_context(user_id: str) -> None:
    """设置用户上下文"""
    user_id_var.set(user_id)


def set_request_context(request_id: str) -> None:
    """设置请求上下文"""
    request_id_var.set(request_id)


# =====================================================================
# Log Level Enum
# =====================================================================


class LogLevel(Enum):
    """日志级别"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# =====================================================================
# Structured Log Record
# =====================================================================


@dataclass
class StructuredLogRecord:
    """结构化日志记录"""

    timestamp: str
    level: str
    message: str
    service: str
    environment: str
    trace_id: str = ""
    span_id: str = ""
    user_id: str = ""
    request_id: str = ""
    module: str = ""
    function: str = ""
    line: int = 0
    extra: Dict[str, Any] = None

    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        data = asdict(self)
        if data.get("extra") is None:
            data["extra"] = {}
        return json.dumps(data, ensure_ascii=False)


# =====================================================================
# JSON Formatter
# =====================================================================


class JSONFormatter(logging.Formatter):
    """JSON 格式日志格式化器"""

    def __init__(
        self, service_name: str = "ai-eval-platform", environment: str = "development"
    ):
        super().__init__()
        self.service_name = service_name
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录为 JSON"""
        # 获取上下文信息
        trace_id = get_trace_id()
        span_id = get_span_id()
        user_id = user_id_var.get()
        request_id = request_id_var.get()

        # 构建结构化日志
        log_record = StructuredLogRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level=record.levelname,
            message=record.getMessage(),
            service=self.service_name,
            environment=self.environment,
            trace_id=trace_id,
            span_id=span_id,
            user_id=user_id,
            request_id=request_id,
            module=record.module,
            function=record.funcName,
            line=record.lineno,
            extra=self._get_extra_fields(record),
        )

        return log_record.to_json()

    def _get_extra_fields(self, record: logging.LogRecord) -> Dict[str, Any]:
        """获取额外字段"""
        extra = {}

        # 添加标准字段
        for key, value in record.__dict__.items():
            if key not in [
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "pathname",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "message",
                "funcName",
            ]:
                extra[key] = value

        # 添加异常信息
        if record.exc_info:
            extra["exception"] = self._format_exception(record.exc_info)

        return extra

    def _format_exception(self, exc_info) -> Dict[str, Any]:
        """格式化异常信息"""
        import traceback

        exc_type, exc_value, exc_tb = exc_info

        return {
            "type": exc_type.__name__ if exc_type else None,
            "message": str(exc_value) if exc_value else None,
            "traceback": traceback.format_exception(exc_type, exc_value, exc_tb),
        }


# =====================================================================
# Console Formatter (带颜色)
# =====================================================================


class ColoredConsoleFormatter(logging.Formatter):
    """带颜色的控制台格式化器"""

    # ANSI 颜色代码
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录"""
        # 获取颜色
        color = self.COLORS.get(record.levelname, self.RESET)

        # 获取上下文
        trace_id = get_trace_id()
        span_id = get_span_id()

        # 构建日志消息
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 基础格式
        base_msg = (
            f"{timestamp} | {color}{record.levelname}{self.RESET} | "
            f"{record.module}:{record.funcName}:{record.lineno}"
        )

        # 添加追踪信息
        if trace_id:
            base_msg += f" | trace:{trace_id[:8]}"
        if span_id:
            base_msg += f" | span:{span_id[:8]}"

        # 添加消息
        base_msg += f" | {record.getMessage()}"

        # 添加异常信息
        if record.exc_info:
            import traceback

            base_msg += f"\n{traceback.format_exception(*record.exc_info)}"

        return base_msg


# =====================================================================
# Logger Configuration
# =====================================================================


class LoggerConfig:
    """日志配置"""

    def __init__(
        self,
        service_name: str = "ai-eval-platform",
        environment: str = "development",
        log_level: str = "INFO",
        json_output: bool = False,
        log_file: Optional[str] = None,
    ):
        self.service_name = service_name
        self.environment = environment
        self.log_level = log_level
        self.json_output = json_output
        self.log_file = log_file

    def setup(self) -> logging.Logger:
        """配置日志系统"""
        # 获取根日志器
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, self.log_level.upper()))

        # 清除现有处理器
        root_logger.handlers.clear()

        # 添加控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        if self.json_output:
            console_handler.setFormatter(
                JSONFormatter(self.service_name, self.environment)
            )
        else:
            console_handler.setFormatter(ColoredConsoleFormatter())
        root_logger.addHandler(console_handler)

        # 添加文件处理器 (如果配置)
        if self.log_file:
            file_handler = logging.FileHandler(self.log_file)
            file_handler.setFormatter(
                JSONFormatter(self.service_name, self.environment)
            )
            root_logger.addHandler(file_handler)

        return root_logger


# =====================================================================
# Logger Factory
# =====================================================================


def get_logger(name: str) -> logging.Logger:
    """获取日志器"""
    return logging.getLogger(name)


def setup_logging(
    service_name: str = "ai-eval-platform",
    environment: str = "development",
    log_level: str = "INFO",
    json_output: bool = False,
    log_file: Optional[str] = None,
) -> logging.Logger:
    """设置日志系统"""
    config = LoggerConfig(
        service_name=service_name,
        environment=environment,
        log_level=log_level,
        json_output=json_output,
        log_file=log_file,
    )
    return config.setup()


# =====================================================================
# Convenience Functions
# =====================================================================


def log_info(message: str, **kwargs) -> None:
    """记录 INFO 日志"""
    logger = get_logger("app")
    logger.info(message, extra=kwargs)


def log_warning(message: str, **kwargs) -> None:
    """记录 WARNING 日志"""
    logger = get_logger("app")
    logger.warning(message, extra=kwargs)


def log_error(message: str, exception: Optional[Exception] = None, **kwargs) -> None:
    """记录 ERROR 日志"""
    logger = get_logger("app")
    if exception:
        logger.error(message, exc_info=True, extra=kwargs)
    else:
        logger.error(message, extra=kwargs)


def log_debug(message: str, **kwargs) -> None:
    """记录 DEBUG 日志"""
    logger = get_logger("app")
    logger.debug(message, extra=kwargs)


def log_critical(message: str, exception: Optional[Exception] = None, **kwargs) -> None:
    """记录 CRITICAL 日志"""
    logger = get_logger("app")
    if exception:
        logger.critical(message, exc_info=True, extra=kwargs)
    else:
        logger.critical(message, extra=kwargs)


# =====================================================================
# Example Usage
# =====================================================================

if __name__ == "__main__":
    # 设置日志系统
    setup_logging(
        service_name="ai-eval-platform",
        environment="development",
        log_level="DEBUG",
        json_output=False,
    )

    # 设置追踪上下文
    set_trace_context("trace-12345", "span-67890")
    set_user_context("user-001")

    # 测试日志
    log_info("系统启动成功")
    log_debug("调试信息", component="api")
    log_warning("资源使用率较高", cpu_usage=85)

    try:
        raise ValueError("测试异常")
    except Exception as e:
        log_error("发生错误", exception=e)
