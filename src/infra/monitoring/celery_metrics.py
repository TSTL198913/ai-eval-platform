"""
Celery任务监控模块

提供异步任务的指标采集和监控功能：
1. 使用Celery signals追踪任务状态转换
2. 支持Pushgateway推送模式（适用于分布式Worker）
3. 队列深度监控
4. 任务执行时间和重试统计
"""

import time
import logging
from typing import Optional, Dict, Any
from celery import signals
from prometheus_client import CollectorRegistry, Counter, Histogram, Gauge

logger = logging.getLogger(__name__)

# 创建独立的Celery指标注册器
CELERY_REGISTRY = CollectorRegistry()

# ============================================================================
# Celery 任务指标定义
# ============================================================================

# 任务状态转换计数器
TASK_STATE_TRANSITIONS = Counter(
    "celery_task_state_transitions_total",
    "Task state transition count",
    ["task_name", "state_from", "state_to"],
    registry=CELERY_REGISTRY,
)

# 任务执行时间直方图
TASK_EXECUTION_TIME = Histogram(
    "celery_task_execution_seconds",
    "Task execution time in seconds",
    ["task_name", "status"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0],
    registry=CELERY_REGISTRY,
)

# 任务重试计数器
TASK_RETRIES = Counter(
    "celery_task_retries_total",
    "Total task retry count",
    ["task_name"],
    registry=CELERY_REGISTRY,
)

# 任务失败计数器
TASK_FAILURES = Counter(
    "celery_task_failures_total",
    "Total task failure count",
    ["task_name", "error_type"],
    registry=CELERY_REGISTRY,
)

# 队列深度Gauge
QUEUE_DEPTH = Gauge(
    "celery_queue_depth",
    "Current queue depth",
    ["queue_name"],
    registry=CELERY_REGISTRY,
)

# Worker数量Gauge
WORKER_COUNT = Gauge(
    "celery_worker_count",
    "Number of active workers",
    registry=CELERY_REGISTRY,
)

# 任务延迟（从提交到开始执行）直方图
TASK_DELAY = Histogram(
    "celery_task_delay_seconds",
    "Task delay from submission to start",
    ["task_name", "queue"],
    buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0],
    registry=CELERY_REGISTRY,
)

# 正在执行的任务数
RUNNING_TASKS = Gauge(
    "celery_running_tasks",
    "Number of tasks currently running",
    ["task_name"],
    registry=CELERY_REGISTRY,
)


# ============================================================================
# 任务状态跟踪
# ============================================================================

class TaskMetricsTracker:
    """任务指标跟踪器"""

    _instance: Optional["TaskMetricsTracker"] = None
    _task_timestamps: Dict[str, float] = {}
    _running_tasks: Dict[str, int] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls) -> "TaskMetricsTracker":
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = TaskMetricsTracker()
        return cls._instance

    def record_submitted(self, task_name: str, task_id: str, timestamp: float, queue: str = "default"):
        """记录任务提交"""
        self._task_timestamps[task_id] = timestamp
        logger.debug(f"Task {task_name}[{task_id}] submitted at {timestamp}")

    def record_started(self, task_name: str, task_id: str, timestamp: float):
        """记录任务开始执行"""
        if task_id in self._task_timestamps:
            delay = timestamp - self._task_timestamps[task_id]
            TASK_DELAY.labels(task_name=task_name, queue="default").observe(delay)
            del self._task_timestamps[task_id]

        # 增加正在运行的任务计数
        key = task_name
        if key not in self._running_tasks:
            self._running_tasks[key] = 0
        self._running_tasks[key] += 1
        RUNNING_TASKS.labels(task_name=task_name).set(self._running_tasks[key])

        logger.debug(f"Task {task_name}[{task_id}] started")

    def record_completed(self, task_name: str, task_id: str, timestamp: float, runtime: float):
        """记录任务完成"""
        TASK_EXECUTION_TIME.labels(task_name=task_name, status="success").observe(runtime)

        # 减少正在运行的任务计数
        key = task_name
        if key in self._running_tasks and self._running_tasks[key] > 0:
            self._running_tasks[key] -= 1
            RUNNING_TASKS.labels(task_name=task_name).set(self._running_tasks[key])

        logger.debug(f"Task {task_name}[{task_id}] completed in {runtime:.2f}s")

    def record_failed(self, task_name: str, task_id: str, timestamp: float, runtime: float, error_type: str):
        """记录任务失败"""
        TASK_EXECUTION_TIME.labels(task_name=task_name, status="failure").observe(runtime)
        TASK_FAILURES.labels(task_name=task_name, error_type=error_type).inc()

        # 减少正在运行的任务计数
        key = task_name
        if key in self._running_tasks and self._running_tasks[key] > 0:
            self._running_tasks[key] -= 1
            RUNNING_TASKS.labels(task_name=task_name).set(self._running_tasks[key])

        logger.debug(f"Task {task_name}[{task_id}] failed: {error_type}")

    def record_retried(self, task_name: str):
        """记录任务重试"""
        TASK_RETRIES.labels(task_name=task_name).inc()
        logger.debug(f"Task {task_name} retry triggered")

    def record_state_transition(self, task_name: str, state_from: str, state_to: str):
        """记录状态转换"""
        TASK_STATE_TRANSITIONS.labels(
            task_name=task_name,
            state_from=state_from,
            state_to=state_to
        ).inc()


# 全局跟踪器实例
_tracker = TaskMetricsTracker.get_instance()


# ============================================================================
# Celery Signals 处理器
# ============================================================================

@signals.task_prerun.connect
def on_task_prerun(sender=None, task_id=None, task=None, *args, **kwargs):
    """任务开始执行前"""
    if task:
        _tracker.record_started(task.name, task_id, time.time())


@signals.task_postrun.connect
def on_task_postrun(sender=None, task_id=None, task=None, state=None, *args, **kwargs):
    """任务执行完成后"""
    if task and hasattr(task, "_start_time"):
        runtime = time.time() - task._start_time
        if state == "SUCCESS":
            _tracker.record_completed(task.name, task_id, time.time(), runtime)
        elif state == "FAILURE":
            error_type = "Unknown"
            if hasattr(task, "result") and isinstance(task.result, Exception):
                error_type = type(task.result).__name__
            _tracker.record_failed(task.name, task_id, time.time(), runtime, error_type)


@signals.task_retry.connect
def on_task_retry(sender=None, task_id=None, task=None, reason=None, *args, **kwargs):
    """任务重试时"""
    if task:
        _tracker.record_retried(task.name)


@signals.task_failure.connect
def on_task_failure(sender=None, task_id=None, exception=None, *args, **kwargs):
    """任务失败时"""
    pass  # 已在postrun中处理


@signals.task_unknown.connect
def on_task_unknown(sender=None, task_id=None, message=None, *args, **kwargs):
    """收到未知任务"""
    logger.warning(f"Unknown task received: {task_id}")


# ============================================================================
# 任务包装器（用于自动记录执行时间）
# ============================================================================

class TrackedTask:
    """包装Celery任务以自动记录指标"""

    def __init__(self, task_func):
        self._task_func = task_func
        self._start_time: Optional[float] = None

    def __call__(self, *args, **kwargs):
        self._start_time = time.time()
        try:
            result = self._task_func(*args, **kwargs)
            return result
        finally:
            self._start_time = None

    @property
    def name(self):
        return getattr(self._task_func, "name", self._task_func.__name__)

    @property
    def _start_time(self):
        return self.__dict__.get("_start_time")

    @_start_time.setter
    def _start_time(self, value):
        self.__dict__["_start_time"] = value


def wrap_task_with_metrics(task_func):
    """装饰器：为任务函数包装指标收集"""
    tracked = TrackedTask(task_func)

    def wrapper(*args, **kwargs):
        return tracked(*args, **kwargs)

    wrapper.name = tracked.name
    wrapper._start_time = None
    return wrapper


# ============================================================================
# Pushgateway 集成
# ============================================================================

class CeleryMetricsExporter:
    """
    Celery指标导出器

    支持两种模式：
    1. Pull模式（默认）：Prometheus直接抓取Worker的/metrics端点
    2. Push模式：使用Pushgateway推送指标（适用于短生命周期Worker）

    使用Push模式时，需要设置环境变量：
    - CELERY_PUSHGATEWAY_URL: Pushgateway地址，如 http://pushgateway:9091
    """

    def __init__(self, pushgateway_url: Optional[str] = None):
        self.pushgateway_url = pushgateway_url or os.getenv("CELERY_PUSHGATEWAY_URL")
        self.use_push = self.pushgateway_url is not None

    def push_metrics(self):
        """推送指标到Pushgateway"""
        if not self.use_push:
            return

        try:
            import httpx
            from prometheus_client import generate_latest

            data = generate_latest(CELERY_REGISTRY)
            response = httpx.post(
                f"{self.pushgateway_url}/metrics/job/celery_tasks",
                data=data,
                headers={"Content-Type": "text/plain"}
            )
            response.raise_for_status()
            logger.debug("Metrics pushed to Pushgateway")
        except Exception as e:
            logger.warning(f"Failed to push metrics to Pushgateway: {e}")


# 全局导出器实例
_exporter: Optional[CeleryMetricsExporter] = None


def get_celery_exporter() -> CeleryMetricsExporter:
    """获取Celery指标导出器"""
    global _exporter
    if _exporter is None:
        _exporter = CeleryMetricsExporter()
    return _exporter


def expose_celery_metrics() -> str:
    """暴露Celery指标（用于Pull模式）"""
    from prometheus_client import generate_latest
    return generate_latest(CELERY_REGISTRY).decode("utf-8")


# ============================================================================
# 队列深度监控
# ============================================================================

def update_queue_depth(queue_name: str, depth: int):
    """更新队列深度"""
    QUEUE_DEPTH.labels(queue_name=queue_name).set(depth)


def update_worker_count(count: int):
    """更新Worker数量"""
    WORKER_COUNT.set(count)


# ============================================================================
# Celerybeat 调度任务监控（可选）
# ============================================================================

SCHEDULED_TASK_RUNTIME = Histogram(
    "celerybeat_scheduled_task_seconds",
    "Scheduled task execution time",
    ["task_name", "schedule_name"],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0],
    registry=CELERY_REGISTRY,
)

SCHEDULED_TASK_INVOCATIONS = Counter(
    "celerybeat_scheduled_task_invocations_total",
    "Scheduled task invocation count",
    ["task_name", "schedule_name", "status"],
    registry=CELERY_REGISTRY,
)


import os
