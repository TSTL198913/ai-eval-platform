"""
Prometheus 指标监控模块

提供评测平台的核心性能指标收集和暴露功能。
"""

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# 创建全局注册器
registry = CollectorRegistry()

# 导入风险监控指标
from . import risk_metrics  # noqa: F401

# 评测指标
EVALUATION_LATENCY = Histogram(
    "evaluation_latency_seconds",
    "Evaluation latency in seconds",
    ["domain", "status"],
    registry=registry,
)

EVALUATION_COUNTER = Counter(
    "evaluation_total",
    "Total number of evaluations",
    ["domain", "status"],
    registry=registry,
)

EVALUATION_ERRORS = Counter(
    "evaluation_errors_total",
    "Total number of evaluation errors",
    ["domain", "error_type"],
    registry=registry,
)

# 任务队列指标
TASK_QUEUE_SIZE = Gauge(
    "task_queue_size",
    "Current size of task queue",
    ["queue_name"],
    registry=registry,
)

TASK_EXECUTION_TIME = Histogram(
    "task_execution_seconds",
    "Task execution time in seconds",
    ["task_name", "status"],
    registry=registry,
)

# 缓冲服务指标
BUFFER_SIZE = Gauge(
    "buffer_size",
    "Current buffer size",
    registry=registry,
)

BUFFER_FLUSH_COUNT = Counter(
    "buffer_flush_total",
    "Total number of buffer flushes",
    ["status"],
    registry=registry,
)

BUFFER_FLUSH_LATENCY = Histogram(
    "buffer_flush_seconds",
    "Buffer flush latency in seconds",
    registry=registry,
)

# 数据库连接指标
DB_CONNECTIONS = Gauge(
    "db_connections",
    "Current database connections",
    ["status"],
    registry=registry,
)

DB_QUERY_LATENCY = Histogram(
    "db_query_seconds",
    "Database query latency in seconds",
    ["query_type"],
    registry=registry,
)

# 限流指标
RATE_LIMITER_TOKENS = Gauge(
    "rate_limiter_tokens",
    "Current rate limiter tokens",
    ["limiter_name"],
    registry=registry,
)

RATE_LIMITER_BLOCKED = Counter(
    "rate_limiter_blocked_total",
    "Total number of blocked requests",
    ["limiter_name"],
    registry=registry,
)


def expose_metrics():
    """暴露 metrics 端点内容"""
    return generate_latest(registry).decode("utf-8")
