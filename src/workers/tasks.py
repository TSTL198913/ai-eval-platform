import atexit
import logging
import os
import signal
import threading
import time

from celery import Task

from src.domain.models.llm_factory import create_llm_client
from src.engine import EvaluationEngine
from src.infra.db.models import EvaluationResultModel
from src.infra.db.session import get_session_local
from src.infra.monitoring.metrics import (
    BUFFER_FLUSH_LATENCY,
    BUFFER_SIZE,
    EVALUATION_COUNTER,
    EVALUATION_ERRORS,
    EVALUATION_LATENCY,
)
from src.schemas.evaluation import EvaluationSchema
from src.schemas.schemas import EvaluationResult
from src.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# 检测是否在测试环境
IS_TESTING = os.environ.get("TESTING", "0") == "1"


class EvaluationBufferService:
    """负责评测结果缓冲与批量落盘。"""

    def __init__(
        self,
        batch_size: int = 1000,
        flush_interval_seconds: float = 30.0,
    ):
        self.buffer: list[EvaluationResultModel] = []
        self.batch_size = batch_size
        self.flush_interval_seconds = flush_interval_seconds
        self.last_flush_time = time.time()
        self._lock = threading.Lock()
        self._closed = False
        self._atexit_registered = False

        # 仅在非测试环境注册进程退出时的 flush
        if not IS_TESTING:
            atexit.register(self._atexit_flush)
            self._atexit_registered = True

            # 注册信号处理，确保 SIGTERM/SIGINT 时也能 flush
            try:
                signal.signal(signal.SIGTERM, self._signal_handler)
                signal.signal(signal.SIGINT, self._signal_handler)
            except (ValueError, OSError):
                # 信号处理可能在非主线程或不支持信号的环境中失败
                pass

    def _signal_handler(self, signum, frame):
        """收到终止信号时执行 flush"""
        logger.info(f"收到信号 {signum}，正在 flush 缓冲区...")
        self.flush()
        self._closed = True

    def _atexit_flush(self):
        """进程退出时自动 flush"""
        if not self._closed and self.buffer:
            logger.info(f"进程退出，flush {len(self.buffer)} 条缓冲记录")
            try:
                self.flush()
            except Exception as e:
                logger.error(f"atexit flush 失败: {e}")

    def add(self, item: EvaluationResultModel) -> int:
        """添加记录到缓冲区"""
        with self._lock:
            self.buffer.append(item)
            self._maybe_time_based_flush()
            return len(self.buffer)

    def _maybe_time_based_flush(self):
        """检查是否需要基于时间的 flush"""
        if self.buffer and time.time() - self.last_flush_time >= self.flush_interval_seconds:
            # 在锁内直接 flush 小批量数据，避免长时间阻塞
            if len(self.buffer) < self.batch_size // 10:  # 小于 10% 批次大小时触发
                try:
                    self._flush_internal()
                except Exception as e:
                    logger.debug(f"Time-based flush failed, will retry later: {str(e)}")

    def add_and_flush_if_needed(self, item: EvaluationResultModel) -> int:
        """添加记录，达到阈值时自动 flush"""
        with self._lock:
            self.buffer.append(item)
            count = len(self.buffer)

            # 达到批次大小时 flush
            if count >= self.batch_size:
                self._flush_internal_unlocked(db_session=None, is_external=False)

            return count

    def flush(self, db_session=None) -> int | None:
        """手动 flush 缓冲区

        Args:
            db_session: 可选的外部 session。如果提供，使用该 session 但不关闭它。
                       如果为 None，创建内部 session 并在完成后关闭。

        Returns:
            flush 的记录数，或 None 如果缓冲区为空
        """
        with self._lock:
            return self._flush_internal_unlocked(
                db_session=db_session,
                is_external=db_session is not None,
            )

    def _flush_internal(self, db_session=None):
        """内部 flush 方法"""
        with self._lock:
            return self._flush_internal_unlocked(
                db_session=db_session,
                is_external=db_session is not None,
            )

    def _flush_internal_unlocked(
        self,
        db_session=None,
        is_external: bool = False,
    ) -> int | None:
        """无锁 flush（必须在持有锁的情况下调用）

        Args:
            db_session: 数据库 session
            is_external: 是否为外部提供的 session

        Returns:
            flush 的记录数，或 None 如果缓冲区为空
        """
        if not self.buffer:
            self.last_flush_time = time.time()
            return None

        batch = list(self.buffer)
        self.buffer = []

        session = db_session if db_session is not None else get_session_local()()
        created_locally = not is_external and db_session is None

        try:
            session.bulk_save_objects(batch)
            session.commit()
            logger.info(f"成功 flush {len(batch)} 条记录到数据库")
            return len(batch)
        except Exception as e:
            logger.error(f"flush 失败，回滚并恢复缓冲区: {e}")
            session.rollback()
            self.buffer = batch + self.buffer
            raise
        finally:
            if created_locally:
                session.close()
            self.last_flush_time = time.time()

    @property
    def buffer_size(self) -> int:
        """获取当前缓冲区大小"""
        with self._lock:
            return len(self.buffer)


buffer_service = EvaluationBufferService()


class WindowsUltimateSoloTask(Task):
    """Celery Task 基类，提供 flush 保护"""

    def flush(self, db_session=None):
        return buffer_service.flush(db_session)

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        """任务完成后（无论成功或失败）尝试 flush 缓冲区"""
        try:
            if buffer_service.buffer_size > 0:
                buffer_service.flush()
        except Exception as e:
            logging.getLogger(__name__).warning(f"after_return flush 失败: {e}")

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """任务失败时记录并尝试 flush"""
        logging.getLogger(__name__).error(f"任务 {task_id} 失败: {exc}")

    def on_success(self, retval, task_id, args, kwargs):
        """任务成功时记录"""
        logging.getLogger(__name__).debug(f"任务 {task_id} 成功完成")

    def on_terminate(self):
        """任务被终止时强制 flush"""
        logging.getLogger(__name__).warning("任务被终止，强制 flush 缓冲区")
        try:
            buffer_service.flush()
        except Exception as e:
            logging.getLogger(__name__).error(f"on_terminate flush 失败: {e}")


def _result_to_model(result: EvaluationResult) -> EvaluationResultModel:
    return EvaluationResultModel(
        case_id=result.case_id,
        model_name=result.model_name,
        adapter_name=result.adapter_name,
        status=result.status.value,
        latency_ms=result.latency_ms,
        response_data=result.response.model_dump() if result.response else {},
    )


@celery_app.task(
    base=WindowsUltimateSoloTask,
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def eval_case_task(self, case_data: dict):
    start_time = time.time()

    try:
        case = EvaluationSchema(**case_data)
        engine = EvaluationEngine(create_llm_client())
        result = engine.run(case)

        # 记录指标
        latency = time.time() - start_time
        EVALUATION_LATENCY.labels(domain=case.type, status=result.status.value).observe(latency)
        EVALUATION_COUNTER.labels(domain=case.type, status=result.status.value).inc()

        db_record = _result_to_model(result)
        count = buffer_service.add(db_record)
        BUFFER_SIZE.set(buffer_service.buffer_size)

        if count >= buffer_service.batch_size:
            flush_start = time.time()
            buffer_service.flush()
            BUFFER_FLUSH_LATENCY.observe(time.time() - flush_start)

        return {
            "status": "success",
            "case_id": case.id,
            "evaluation_status": result.status.value,
            "latency_ms": result.latency_ms,
        }
    except Exception as e:
        # 记录错误指标
        latency = time.time() - start_time
        case_type = case.type if 'case' in locals() else 'unknown'
        EVALUATION_LATENCY.labels(domain=case_type, status='error').observe(latency)
        EVALUATION_ERRORS.labels(domain=case_type, error_type=type(e).__name__).inc()
        raise
