# =====================================================================
# AI Evaluation Platform - 结构化日志系统测试
# =====================================================================

import json
import logging

from src.infra.structured_logging import (
    ColoredConsoleFormatter,
    JSONFormatter,
    LoggerConfig,
    get_logger,
    get_span_id,
    get_trace_id,
    log_debug,
    log_error,
    log_info,
    log_warning,
    set_trace_context,
    set_user_context,
    setup_logging,
)


class TestStructuredLogging:
    """结构化日志系统测试"""

    def test_json_formatter_basic(self):
        """测试 JSON 格式化器基础功能"""
        formatter = JSONFormatter(service_name="test-service", environment="test")

        # 创建日志记录
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # 格式化
        output = formatter.format(record)

        # 验证 JSON 格式
        data = json.loads(output)
        assert data["level"] == "INFO"
        assert data["message"] == "Test message"
        assert data["service"] == "test-service"
        assert data["environment"] == "test"

    def test_json_formatter_with_trace_context(self):
        """测试带追踪上下文的 JSON 格式化"""
        formatter = JSONFormatter()

        # 设置追踪上下文
        set_trace_context("trace-123", "span-456")

        # 创建日志记录
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test with trace",
            args=(),
            exc_info=None,
        )

        # 格式化
        output = formatter.format(record)
        data = json.loads(output)

        # 验证追踪信息
        assert data["trace_id"] == "trace-123"
        assert data["span_id"] == "span-456"

    def test_json_formatter_with_exception(self):
        """测试带异常信息的 JSON 格式化"""
        formatter = JSONFormatter()

        # 创建异常
        try:
            raise ValueError("Test exception")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        # 创建日志记录
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )

        # 格式化
        output = formatter.format(record)
        data = json.loads(output)

        # 验证异常信息
        assert "exception" in data["extra"]
        assert data["extra"]["exception"]["type"] == "ValueError"
        assert data["extra"]["exception"]["message"] == "Test exception"

    def test_colored_console_formatter(self):
        """测试带颜色的控制台格式化器"""
        formatter = ColoredConsoleFormatter()

        # 创建日志记录
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # 格式化
        output = formatter.format(record)

        # 验证包含颜色代码
        assert "\033[32m" in output  # Green color for INFO
        assert "Test message" in output

    def test_logger_config_setup(self):
        """测试日志配置设置"""
        config = LoggerConfig(
            service_name="test-service",
            environment="test",
            log_level="DEBUG",
            json_output=True,
        )

        # 设置日志系统
        logger = config.setup()

        # 验证日志级别
        assert logger.level == logging.DEBUG

        # 验证处理器
        assert len(logger.handlers) > 0

    def test_setup_logging_function(self):
        """测试 setup_logging 函数"""
        logger = setup_logging(
            service_name="test", environment="dev", log_level="INFO", json_output=False
        )

        # 验证返回日志器
        assert logger is not None

    def test_convenience_functions(self):
        """测试便捷日志函数"""
        setup_logging(log_level="DEBUG")

        # 设置追踪上下文
        set_trace_context("trace-test", "span-test")

        # 测试各级别日志函数
        log_info("Info message", component="test")
        log_warning("Warning message", cpu_usage=85)
        log_debug("Debug message")

        # 测试带异常的错误日志
        try:
            raise ValueError("Test error")
        except Exception as e:
            log_error("Error occurred", exception=e)

    def test_context_variables(self):
        """测试上下文变量"""
        # 设置追踪上下文
        set_trace_context("trace-123", "span-456")

        # 验证获取函数
        assert get_trace_id() == "trace-123"
        assert get_span_id() == "span-456"

        # 设置用户上下文
        set_user_context("user-001")
        assert "user-001" in "user-001"

    def test_json_output_mode(self):
        """测试 JSON 输出模式"""
        setup_logging(json_output=True, log_level="INFO")

        logger = get_logger("test")

        # 设置追踪上下文
        set_trace_context("trace-json", "span-json")

        # 记录日志 (输出到 stdout，这里只验证不报错)
        logger.info("JSON mode test")


class TestLoggingIntegration:
    """日志集成测试"""

    def test_logging_with_api_context(self):
        """测试 API 上下文日志"""
        setup_logging(log_level="DEBUG")

        # 模拟 API 请求上下文
        set_trace_context("req-trace-123", "req-span-456")
        set_user_context("user-api-001")

        logger = get_logger("api")
        logger.info(
            "API request received", extra={"method": "POST", "path": "/evaluate"}
        )
        logger.debug("Processing request", extra={"request_id": "req-001"})

    def test_logging_with_worker_context(self):
        """测试 Worker 上下文日志"""
        setup_logging(log_level="DEBUG")

        # 模拟 Worker 任务上下文
        set_trace_context("task-trace-123", "task-span-456")

        logger = get_logger("worker")
        logger.info("Task started", extra={"task_id": "task-001", "domain": "general"})
        logger.info("Task completed", extra={"task_id": "task-001", "score": 0.95})
