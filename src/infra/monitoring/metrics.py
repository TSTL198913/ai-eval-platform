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

# 路由指标
ROUTING_DECISION_COUNTER = Counter(
    "routing_decisions_total",
    "Total number of model routing decisions",
    ["task_type", "provider", "source"],
    registry=registry,
)

ROUTING_LATENCY = Histogram(
    "routing_latency_seconds",
    "Model routing latency in seconds",
    ["task_type", "source"],
    registry=registry,
)

# ===================== 状态机监控指标 =====================
EVAL_STATUS_COUNTER = Counter(
    "eval_status_total",
    "Total number of evaluation status transitions",
    ["evaluator", "status"],
    registry=registry,
)

EVAL_STATUS_TRANSITIONS = Counter(
    "eval_status_transitions_total",
    "Total number of status transitions",
    ["from_status", "to_status"],
    registry=registry,
)

EVAL_CONFIDENCE_HISTOGRAM = Histogram(
    "eval_confidence_distribution",
    "Distribution of evaluation confidence scores",
    ["evaluator", "confidence_level"],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
    registry=registry,
)

EVAL_FIELD_ACCESS_COUNTER = Counter(
    "eval_field_access_total",
    "Total number of field accesses",
    ["evaluator", "field_name"],
    registry=registry,
)


def expose_metrics():
    """暴露 metrics 端点内容"""
    return generate_latest(registry).decode("utf-8")
