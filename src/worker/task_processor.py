"""
分布式任务处理器

集成:
- 分布式锁 (防止任务重复执行)
- 熔断器 (保护下游服务)
- 追踪 (OpenTelemetry)
- 指标 (Prometheus)
- 重试机制 (指数退避)
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional

from src.distributed.circuit_breaker import CircuitBreaker, CircuitBreakerError, CircuitBreakerConfig
from src.distributed.lock import DistributedLock, LockState
from src.distributed.queue import QueueMessage
from src.llm.base import LLMConfig, create_llm_client
from src.metrics import get_registry
from src.tracing import TraceContext, get_tracer

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    REJECTED = "rejected"  # 被限流或熔断拒绝


@dataclass
class TaskContext:
    """任务执行上下文"""
    task_id: str
    case_id: str
    domain: str
    payload: Dict[str, Any]
    retry_count: int = 0
    max_retries: int = 3
    trace_id: Optional[str] = None
    worker_id: Optional[str] = None
    started_at: Optional[float] = None
    finished_at: Optional[float] = None

    @property
    def latency_ms(self) -> float:
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at) * 1000
        return 0.0


@dataclass
class TaskResult:
    """任务执行结果"""
    task_id: str
    case_id: str
    status: TaskStatus
    score: Optional[float] = None
    response_text: Optional[str] = None
    error_message: Optional[str] = None
    latency_ms: float = 0.0
    trace_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class DistributedTaskProcessor:
    """
    分布式任务处理器

    特性:
    - 分布式锁防止重复执行
    - 熔断器保护
    - 自动重试
    - 指标采集
    - 追踪集成
    """

    def __init__(
        self,
        redis_client,
        llm_config: Optional[LLMConfig] = None,
        worker_id: Optional[str] = None,
    ):
        self.redis = redis_client
        self.llm_config = llm_config or LLMConfig()
        self.worker_id = worker_id or str(uuid.uuid4())[:8]
        self._metrics = get_registry()
        self._tracer = get_tracer()

        # 熔断器
        self._circuit_breaker = CircuitBreaker(
            f"worker_{self.worker_id}",
            CircuitBreakerConfig(
                failure_threshold=5,
                success_threshold=2,
                timeout_seconds=30.0,
            ),
        )

    async def process_task(
        self,
        task: QueueMessage,
        evaluator_func: Callable,
    ) -> TaskResult:
        """
        处理单个任务

        Args:
            task: 队列消息
            evaluator_func: 评测函数 (domain, payload, llm_client) -> result

        Returns:
            TaskResult: 任务结果
        """
        # 解析任务
        case_id = task.payload.get("case_id", "unknown")
        task_id = task.message_id

        ctx = TaskContext(
            task_id=task_id,
            case_id=case_id,
            domain=task.payload.get("domain", "general"),
            payload=task.payload,
            retry_count=task.retry_count,
            max_retries=task.max_retries,
            trace_id=task.trace_id,
            worker_id=self.worker_id,
        )

        # 尝试获取分布式锁 (防止重复执行)
        lock = DistributedLock(
            self.redis,
            f"task:{case_id}",
            ttl_seconds=60.0,
            retry_times=1,
        )
        lock_result = lock.acquire()

        if lock_result.state != LockState.ACQUIRED:
            logger.warning(f"Task {task_id} already being processed by another worker")
            return TaskResult(
                task_id=task_id,
                case_id=case_id,
                status=TaskStatus.REJECTED,
                error_message="Task already being processed",
            )

        try:
            return await self._execute_task(ctx, evaluator_func)
        finally:
            lock.release()

    async def _execute_task(
        self,
        ctx: TaskContext,
        evaluator_func: Callable,
    ) -> TaskResult:
        """执行任务主体"""
        start_time = time.time()
        ctx.started_at = start_time

        # 创建追踪上下文
        with TraceContext(self._tracer, f"eval.{ctx.domain}") as trace_ctx:
            trace_ctx.span.set_attribute("case_id", ctx.case_id)
            trace_ctx.span.set_attribute("worker_id", self.worker_id)
            trace_ctx.span.set_attribute("retry_count", ctx.retry_count)

            try:
                # 检查熔断器
                if self._circuit_breaker.is_open:
                    raise CircuitBreakerError("Circuit breaker is open")

                # 创建 LLM 客户端
                llm_client = create_llm_client(
                    provider=ctx.payload.get("provider"),
                    model_name=ctx.payload.get("model"),
                )

                # 执行评测
                result = await evaluator_func(
                    domain=ctx.domain,
                    payload=ctx.payload,
                    llm_client=llm_client,
                )

                ctx.finished_at = time.time()
                latency_ms = (ctx.finished_at - start_time) * 1000

                # 更新指标
                self._record_success(ctx.domain, latency_ms)

                return TaskResult(
                    task_id=ctx.task_id,
                    case_id=ctx.case_id,
                    status=TaskStatus.PASSED if result.get("is_valid") else TaskStatus.FAILED,
                    score=result.get("score"),
                    response_text=result.get("text"),
                    latency_ms=latency_ms,
                    trace_id=trace_ctx.span.trace_id,
                    metadata=result.get("metadata", {}),
                )

            except CircuitBreakerError as e:
                ctx.finished_at = time.time()
                logger.warning(f"Circuit breaker open for task {ctx.task_id}: {e}")
                self._record_rejected(ctx.domain)

                # 判断是否应该重试
                if ctx.retry_count < ctx.max_retries:
                    return TaskResult(
                        task_id=ctx.task_id,
                        case_id=ctx.case_id,
                        status=TaskStatus.ERROR,
                        error_message=f"Circuit breaker open: {e}",
                        latency_ms=(ctx.finished_at - start_time) * 1000,
                        metadata={"should_retry": True},
                    )
                return TaskResult(
                    task_id=ctx.task_id,
                    case_id=ctx.case_id,
                    status=TaskStatus.REJECTED,
                    error_message=f"Circuit breaker open: {e}",
                    latency_ms=(ctx.finished_at - start_time) * 1000,
                )

            except Exception as e:
                ctx.finished_at = time.time()
                latency_ms = (ctx.finished_at - start_time) * 1000

                logger.error(f"Task {ctx.task_id} failed: {e}", exc_info=True)

                # 更新熔断器
                self._circuit_breaker._record_failure()

                # 更新指标
                self._record_error(ctx.domain, type(e).__name__)

                # 判断是否应该重试
                should_retry = ctx.retry_count < ctx.max_retries

                return TaskResult(
                    task_id=ctx.task_id,
                    case_id=ctx.case_id,
                    status=TaskStatus.ERROR,
                    error_message=str(e),
                    latency_ms=latency_ms,
                    metadata={"should_retry": should_retry},
                )

    def _record_success(self, domain: str, latency_ms: float) -> None:
        """记录成功指标"""
        try:
            counter = self._metrics.get_metric("eval_tasks_total")
            if counter:
                counter.inc(domain=domain, status="success")

            histogram = self._metrics.get_metric("eval_task_duration_seconds")
            if histogram:
                histogram.observe(latency_ms / 1000, domain=domain)
        except Exception as e:
            logger.debug(f"Failed to record metrics: {e}")

    def _record_error(self, domain: str, error_type: str) -> None:
        """记录错误指标"""
        try:
            counter = self._metrics.get_metric("eval_task_errors_total")
            if counter:
                counter.inc(domain=domain, error_type=error_type)
        except Exception as e:
            logger.debug(f"Failed to record metrics: {e}")

    def _record_rejected(self, domain: str) -> None:
        """记录被拒绝的指标"""
        try:
            counter = self._metrics.get_metric("eval_tasks_total")
            if counter:
                counter.inc(domain=domain, status="rejected")
        except Exception as e:
            logger.debug(f"Failed to record metrics: {e}")


class RetryPolicy:
    """
    重试策略

    支持:
    - 固定间隔
    - 指数退避
    - 抖动
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def get_delay(self, attempt: int) -> float:
        """获取重试延迟"""
        import random

        delay = min(
            self.base_delay * (self.exponential_base ** attempt),
            self.max_delay,
        )

        if self.jitter:
            delay = delay * (0.5 + random.random() * 0.5)

        return delay

    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        **kwargs,
    ) -> Any:
        """带重试执行函数"""
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries:
                    delay = self.get_delay(attempt)
                    logger.warning(
                        f"Attempt {attempt + 1} failed, retrying in {delay:.2f}s: {e}"
                    )
                    await asyncio.sleep(delay)

        raise last_exception
