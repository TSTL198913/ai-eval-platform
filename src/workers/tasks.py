import atexit
import logging
import os
import signal
import threading
import time
from typing import Any, Dict, Optional

from src.infra.db.models import EvaluationResultModel
from src.infra.db.session import get_session_local
from src.schemas.evaluation import EvaluationSchema
from src.schemas.schemas import EvaluationResult


def _get_evaluation_engine(llm_client=None):
    """延迟获取EvaluationEngine"""
    from src.engine import EvaluationEngine
    from src.domain.models.llm_factory import create_llm_client
    return EvaluationEngine(create_llm_client(client=llm_client))

logger = logging.getLogger(__name__)

IS_TESTING = os.environ.get("TESTING", "0") == "1"

# 缓冲配置（支持环境变量覆盖）
BUFFER_BATCH_SIZE = int(os.environ.get("BUFFER_BATCH_SIZE", "100"))
BUFFER_FLUSH_INTERVAL = float(os.environ.get("BUFFER_FLUSH_INTERVAL", "5.0"))
# 缓冲优化：自适应批量大小配置
BUFFER_ADAPTIVE_BATCH_SIZE = bool(os.environ.get("BUFFER_ADAPTIVE_BATCH_SIZE", "true").lower() == "true")
BUFFER_MIN_BATCH_SIZE = int(os.environ.get("BUFFER_MIN_BATCH_SIZE", "10"))
BUFFER_MAX_BATCH_SIZE = int(os.environ.get("BUFFER_MAX_BATCH_SIZE", "500"))
# 优先级缓冲配置
BUFFER_PRIORITY_ENABLED = bool(os.environ.get("BUFFER_PRIORITY_ENABLED", "false").lower() == "true")

# 任务重试策略配置（支持环境变量覆盖）
TASK_MAX_RETRIES = int(os.environ.get("CELERY_TASK_MAX_RETRIES", "3"))
TASK_RETRY_BACKOFF = os.environ.get("CELERY_TASK_RETRY_BACKOFF", "true").lower() == "true"
TASK_RETRY_BACKOFF_MAX = int(os.environ.get("CELERY_TASK_RETRY_BACKOFF_MAX", "600"))
TASK_RETRY_JITTER = os.environ.get("CELERY_TASK_RETRY_JITTER", "true").lower() == "true"
TASK_DEFAULT_RETRY_DELAY = int(os.environ.get("CELERY_TASK_DEFAULT_RETRY_DELAY", "3"))

# 任务超时配置
TASK_TIME_LIMIT = int(os.environ.get("CELERY_TASK_TIME_LIMIT", "60"))
TASK_SOFT_TIME_LIMIT = int(os.environ.get("CELERY_TASK_SOFT_TIME_LIMIT", "240"))

_METRICS: Optional[Dict[str, Any]] = None
_TASK = None
_CELERY_APP = None


def _get_metrics() -> Dict[str, Any]:
    global _METRICS
    if _METRICS is None:
        from src.infra.monitoring.metrics import (
            BUFFER_FLUSH_LATENCY,
            BUFFER_SIZE,
            EVALUATION_COUNTER,
            EVALUATION_ERRORS,
            EVALUATION_LATENCY,
        )
        _METRICS = {
            "BUFFER_FLUSH_LATENCY": BUFFER_FLUSH_LATENCY,
            "BUFFER_SIZE": BUFFER_SIZE,
            "EVALUATION_COUNTER": EVALUATION_COUNTER,
            "EVALUATION_ERRORS": EVALUATION_ERRORS,
            "EVALUATION_LATENCY": EVALUATION_LATENCY,
        }
    return _METRICS


def _get_Task():
    global _TASK
    if _TASK is None:
        from celery import Task
        _TASK = Task
    return _TASK


def _get_celery_app():
    global _CELERY_APP
    if _CELERY_APP is None:
        from src.workers.celery_app import get_celery_app
        _CELERY_APP = get_celery_app()
    return _CELERY_APP


class EvaluationBufferService:
    """负责评测结果缓冲与批量落盘。

    优化特性：
    - 自适应批量大小：根据系统负载动态调整批量大小
    - 优先级缓冲：高优先级任务优先处理
    - 线程安全：使用锁保护共享状态
    - Session复用：支持外部传入session进行复用
    - 异常恢复：flush失败时自动恢复缓冲区数据
    """

    def __init__(
        self,
        batch_size: int = BUFFER_BATCH_SIZE,
        flush_interval_seconds: float = BUFFER_FLUSH_INTERVAL,
        adaptive_batch_size: bool = BUFFER_ADAPTIVE_BATCH_SIZE,
        min_batch_size: int = BUFFER_MIN_BATCH_SIZE,
        max_batch_size: int = BUFFER_MAX_BATCH_SIZE,
        priority_enabled: bool = BUFFER_PRIORITY_ENABLED,
    ):
        self.buffer: list[EvaluationResultModel] = []
        self.priority_buffer: list[EvaluationResultModel] = []  # 高优先级缓冲
        self.batch_size = batch_size
        self.flush_interval_seconds = flush_interval_seconds
        self.last_flush_time = time.time()
        self._lock = threading.Lock()
        self._closed = False
        self._atexit_registered = False
        # 自适应批量配置
        self.adaptive_batch_size = adaptive_batch_size
        self.min_batch_size = min_batch_size
        self.max_batch_size = max_batch_size
        self._current_batch_size = batch_size
        # 优先级缓冲配置
        self.priority_enabled = priority_enabled
        # Session复用：存储可复用的session
        self._reusable_session = None
        # 统计信息
        self._total_flush_count = 0
        self._total_flush_latency = 0.0

        if not IS_TESTING:
            atexit.register(self._atexit_flush)
            self._atexit_registered = True

            try:
                signal.signal(signal.SIGTERM, self._signal_handler)
                signal.signal(signal.SIGINT, self._signal_handler)
            except (ValueError, OSError):
                pass

    def _get_adaptive_batch_size(self) -> int:
        """根据当前缓冲区大小动态调整批量大小"""
        if not self.adaptive_batch_size:
            return self.batch_size

        buffer_len = len(self.buffer) + len(self.priority_buffer)
        if buffer_len < self.min_batch_size:
            return self.min_batch_size
        elif buffer_len > self.max_batch_size:
            return self.max_batch_size
        else:
            # 线性调整： buffer_len * 1.2，上限为 max_batch_size
            return min(int(buffer_len * 1.2), self.max_batch_size)

    def _signal_handler(self, signum, frame):
        logger.info(f"收到信号 {signum}，正在 flush 缓冲区...")
        self.flush()
        self._closed = True

    def _atexit_flush(self):
        if not self._closed and (self.buffer or self.priority_buffer):
            total = len(self.buffer) + len(self.priority_buffer)
            logger.info(f"进程退出，flush {total} 条缓冲记录")
            try:
                self.flush()
            except Exception as e:
                logger.error(f"atexit flush 失败: {e}")

    def get_or_create_session(self):
        """获取或创建可复用的数据库session"""
        if self._reusable_session is None:
            self._reusable_session = get_session_local()()
        return self._reusable_session

    def close_reusable_session(self):
        """关闭可复用的session"""
        if self._reusable_session is not None:
            try:
                self._reusable_session.close()
            except Exception as e:
                logger.warning(f"关闭session失败: {e}")
            finally:
                self._reusable_session = None

    def add(self, item: EvaluationResultModel, priority: bool = False) -> int:
        """添加记录到缓冲区

        Args:
            item: 评测结果模型
            priority: 是否为高优先级任务
        """
        with self._lock:
            if priority and self.priority_enabled:
                self.priority_buffer.append(item)
                self._maybe_time_based_flush(priority_buffer=True)
            else:
                self.buffer.append(item)
                self._maybe_time_based_flush(priority_buffer=False)
            return len(self.buffer) + len(self.priority_buffer)

    def _maybe_time_based_flush(self, priority_buffer: bool = False):
        """检查是否需要基于时间触发flush

        Args:
            priority_buffer: 是否检查优先级缓冲区
        """
        buffer = self.priority_buffer if priority_buffer else self.buffer
        if buffer and time.time() - self.last_flush_time >= self.flush_interval_seconds:
            adaptive_size = self._get_adaptive_batch_size()
            if len(buffer) < adaptive_size // 10:
                batch = None
                with self._lock:
                    if len(buffer) < adaptive_size // 10:
                        batch = list(buffer)
                        buffer.clear()
                if batch:
                    try:
                        self._flush_batch(batch)
                    except Exception as e:
                        logger.debug(f"Time-based flush failed: {e}")
                        with self._lock:
                            buffer.extend(batch)

    def _flush_batch(self, batch: list[EvaluationResultModel], session=None) -> int:
        """在锁外执行实际的数据库flush操作

        Args:
            batch: 要flush的批次数据
            session: 可选的外部session，用于session复用
        """
        use_external_session = session is not None
        if session is None:
            session = get_session_local()()
        try:
            session.bulk_save_objects(batch)
            session.commit()
            logger.info(f"成功 flush {len(batch)} 条记录到数据库")
            return len(batch)
        except Exception as e:
            logger.error(f"flush 失败: {e}")
            session.rollback()
            raise
        finally:
            # 只有在非外部session时才关闭
            if not use_external_session:
                session.close()

    def add_and_flush_if_needed(self, item: EvaluationResultModel, priority: bool = False) -> int:
        """添加记录并检查是否需要flush

        Args:
            item: 评测结果模型
            priority: 是否为高优先级任务
        """
        with self._lock:
            if priority and self.priority_enabled:
                self.priority_buffer.append(item)
                count = len(self.buffer) + len(self.priority_buffer)
            else:
                self.buffer.append(item)
                count = len(self.buffer) + len(self.priority_buffer)

            adaptive_batch_size = self._get_adaptive_batch_size()
            should_flush = len(self.buffer) >= adaptive_batch_size or (
                priority and self.priority_enabled and len(self.priority_buffer) >= adaptive_batch_size
            )

            if should_flush:
                batch = list(self.buffer)
                priority_batch = list(self.priority_buffer) if self.priority_enabled else []
                self.buffer = []
                self.priority_buffer = []

        if should_flush:
            try:
                if batch:
                    self._flush_batch(batch)
                if priority_batch:
                    self._flush_batch(priority_batch)
            except Exception:
                # 异常恢复：在锁内恢复缓冲区
                with self._lock:
                    self.buffer = batch + self.buffer
                    self.priority_buffer = priority_batch + self.priority_buffer
                raise

        return count

    def flush(self, db_session=None) -> int | None:
        """Flush所有缓冲区（普通缓冲区和优先级缓冲区）

        Args:
            db_session: 可选的外部数据库session，用于session复用

        Returns:
            flush的记录数，如果缓冲区为空则返回None

        Note:
            - 支持外部传入session实现session复用
            - flush失败时会自动恢复缓冲区数据（异常恢复机制）
            - 使用锁保护缓冲区操作，避免竞态条件
        """
        batch = None
        priority_batch = None
        # 在锁内取出数据并清空缓冲区
        with self._lock:
            if not self.buffer and not self.priority_buffer:
                self.last_flush_time = time.time()
                return None
            batch = list(self.buffer)
            priority_batch = list(self.priority_buffer)
            self.buffer = []
            self.priority_buffer = []
            self.last_flush_time = time.time()

        total_count = 0
        if batch or priority_batch:
            flush_start = time.time()
            try:
                if batch:
                    if db_session is not None:
                        db_session.bulk_save_objects(batch)
                        db_session.commit()
                    else:
                        self._flush_batch(batch)
                    total_count += len(batch)
                if priority_batch:
                    if db_session is not None:
                        db_session.bulk_save_objects(priority_batch)
                        db_session.commit()
                    else:
                        self._flush_batch(priority_batch)
                    total_count += len(priority_batch)
                # 更新统计信息
                self._total_flush_count += 1
                self._total_flush_latency += time.time() - flush_start
                logger.info(f"成功 flush {total_count} 条记录到数据库")
            except Exception as e:
                logger.error(f"flush 失败，回滚并恢复缓冲区: {e}")
                if db_session:
                    db_session.rollback()
                # 异常恢复：在锁内恢复缓冲区数据
                with self._lock:
                    self.buffer = batch + self.buffer
                    self.priority_buffer = priority_batch + self.priority_buffer
                raise
            return total_count
        return None

    @property
    def buffer_size(self) -> int:
        """返回当前缓冲区大小（普通+优先级）"""
        with self._lock:
            return len(self.buffer) + len(self.priority_buffer)

    @property
    def priority_buffer_size(self) -> int:
        """返回优先级缓冲区大小"""
        with self._lock:
            return len(self.priority_buffer)

    def get_flush_stats(self) -> Dict[str, Any]:
        """获取flush统计信息"""
        with self._lock:
            avg_latency = self._total_flush_latency / self._total_flush_count if self._total_flush_count > 0 else 0.0
            return {
                "total_flush_count": self._total_flush_count,
                "avg_flush_latency": avg_latency,
                "current_batch_size": self._current_batch_size,
            }

    def reset_stats(self):
        """重置统计信息"""
        with self._lock:
            self._total_flush_count = 0
            self._total_flush_latency = 0.0


buffer_service = EvaluationBufferService()


class _TaskBase:
    """Task基类，提供flush保护"""

    def flush(self, db_session=None):
        return buffer_service.flush(db_session)

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        try:
            if buffer_service.buffer_size > 0:
                buffer_service.flush()
        except Exception as e:
            logger.warning(f"after_return flush 失败: {e}")

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f"任务 {task_id} 失败: {exc}")

    def on_success(self, retval, task_id, args, kwargs):
        logger.debug(f"任务 {task_id} 成功完成")

    def on_terminate(self):
        logger.warning("任务被终止，强制 flush 缓冲区")
        try:
            buffer_service.flush()
        except Exception as e:
            logger.error(f"on_terminate flush 失败: {e}")


def _create_task_base():
    """创建生产环境Task基类"""
    Task = _get_Task()
    return type('WindowsUltimateSoloTask', (Task, _TaskBase), {})


WindowsUltimateSoloTask = _create_task_base() if not IS_TESTING else _TaskBase


def _result_to_model(result: EvaluationResult) -> EvaluationResultModel:
    return EvaluationResultModel(
        case_id=result.case_id,
        model_name=result.model_name,
        adapter_name=result.adapter_name,
        status=result.status.value,
        latency_ms=result.latency_ms,
        response_data=result.response.model_dump() if result.response else {},
    )


def _register_task(**kwargs):
    """注册Celery任务"""
    if IS_TESTING:
        def mock_task_decorator(func):
            class MockAsyncResult:
                def __init__(self, task_id, result):
                    self.id = task_id
                    self._result = result
                    self.state = "SUCCESS"

                def ready(self):
                    return True

                @property
                def result(self):
                    return self._result

                def get(self, timeout=None):
                    return self._result

            class MockTaskWrapper(_TaskBase):
                _wrapped_func = func
                _task_counter = 0

                def delay(self, *args, **kwargs):
                    MockTaskWrapper._task_counter += 1
                    task_id = f"test-task-{MockTaskWrapper._task_counter}"
                    result = func(self, *args, **kwargs)
                    return MockAsyncResult(task_id, result)

                def apply_async(self, args=None, kwargs=None, **_):
                    args = args or ()
                    kwargs = kwargs or {}
                    MockTaskWrapper._task_counter += 1
                    task_id = f"test-task-{MockTaskWrapper._task_counter}"
                    result = func(self, *args, **kwargs)
                    return MockAsyncResult(task_id, result)

            return MockTaskWrapper()

        return mock_task_decorator

    app = _get_celery_app()
    return app.task(**kwargs)


@_register_task(
    base=WindowsUltimateSoloTask,
    bind=True,
    # 重试策略配置
    max_retries=TASK_MAX_RETRIES,
    autoretry_for=(Exception,),
    retry_backoff=TASK_RETRY_BACKOFF,
    retry_backoff_max=TASK_RETRY_BACKOFF_MAX,
    retry_jitter=TASK_RETRY_JITTER,
    default_retry_delay=TASK_DEFAULT_RETRY_DELAY,
    # 超时控制
    time_limit=TASK_TIME_LIMIT,
    soft_time_limit=TASK_SOFT_TIME_LIMIT,
    # 任务追踪
    track_started=True,
)
def eval_case_task(self, case_data: dict, priority: bool = False, llm_client=None) -> Dict[str, Any]:
    """评测任务

    Args:
        case_data: 评测用例数据
        priority: 是否为高优先级任务
        llm_client: 可选的LLM客户端，用于测试模式

    超时控制：
        - time_limit: 硬超时，超过后任务被强制终止
        - soft_time_limit: 软超时，超过后抛出异常，可通过重试恢复

    重试策略：
        - 指数退避：retry_backoff=True 时使用
        - 最大退避时间：retry_backoff_max=600秒
        - 抖动：retry_jitter=True 添加随机抖动避免惊群效应
    """
    start_time = time.time()
    metrics = None if IS_TESTING else _get_metrics()
    case_type = "unknown"

    try:
        case = EvaluationSchema(**case_data)
        case_type = case.type
        engine = _get_evaluation_engine(llm_client=llm_client)
        result = engine.run(case)

        if metrics:
            latency = time.time() - start_time
            metrics["EVALUATION_LATENCY"].labels(domain=case_type, status=result.status.value).observe(latency)
            metrics["EVALUATION_COUNTER"].labels(domain=case_type, status=result.status.value).inc()

        db_record = _result_to_model(result)
        # 支持优先级缓冲
        count = buffer_service.add(db_record, priority=priority)

        if metrics:
            metrics["BUFFER_SIZE"].set(buffer_service.buffer_size)

            adaptive_batch_size = buffer_service._get_adaptive_batch_size()
            if count >= adaptive_batch_size:
                flush_start = time.time()
                buffer_service.flush()
                metrics["BUFFER_FLUSH_LATENCY"].observe(time.time() - flush_start)

        return {
            "status": "success",
            "case_id": case.id,
            "evaluation_status": result.status.value,
            "latency_ms": result.latency_ms,
        }
    except Exception as e:
        if metrics:
            latency = time.time() - start_time
            metrics["EVALUATION_LATENCY"].labels(domain=case_type, status="error").observe(latency)
            metrics["EVALUATION_ERRORS"].labels(domain=case_type, error_type=type(e).__name__).inc()
        raise