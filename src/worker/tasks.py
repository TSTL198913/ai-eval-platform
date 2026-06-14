"""
Celery 任务定义

包含:
- eval_case_task: 评测任务
- flush_buffer: 缓冲区刷新
"""

import logging
import os
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from src.distributed.circuit_breaker import global_registry
from src.infra.db.models import EvaluationResultModel
from src.infra.db.session import SessionLocal
from src.metrics import get_registry
from src.schemas.evaluation import EvaluationSchema
from src.worker.celery_app import EvalTask, celery_app, get_redis_client
from src.worker.task_processor import DistributedTaskProcessor, TaskResult

logger = logging.getLogger(__name__)


# =====================================================================
# 1. 结果缓冲区服务
# =====================================================================

class EvaluationBufferService:
    """
    评测结果缓冲与批量写入服务

    特性:
    - 线程安全
    - 批量写入减少数据库压力
    - 异常时数据恢复
    - 定期自动刷新
    """

    def __init__(self, batch_size: int = 100, flush_interval: float = 5.0):
        self.buffer: List[EvaluationResultModel] = []
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.last_flush_time = time.time()
        self._lock = threading.Lock()
        self._metrics = get_registry()

    def add(self, item: EvaluationResultModel) -> int:
        """添加结果到缓冲区"""
        with self._lock:
            self.buffer.append(item)
            count = len(self.buffer)

        # 记录指标
        try:
            gauge = self._metrics.get_metric("buffer_size")
            if gauge:
                gauge.set(count)
        except Exception:
            pass

        return count

    def flush(self, db_session=None) -> int:
        """
        刷新缓冲区，批量写入数据库

        Returns:
            写入的记录数
        """
        with self._lock:
            if not self.buffer:
                return 0
            batch = list(self.buffer)
            self.buffer = []

        is_external_session = db_session is not None
        db = db_session if db_session else SessionLocal()

        try:
            db.bulk_save_objects(batch)
            db.commit()

            logger.info(f"Flushed {len(batch)} records to database")
            return len(batch)

        except Exception as e:
            logger.error(f"Failed to flush buffer: {e}")
            # 数据恢复
            with self._lock:
                self.buffer = batch + self.buffer
            db.rollback()
            raise

        finally:
            if not is_external_session:
                db.close()

            self.last_flush_time = time.time()

    def get_size(self) -> int:
        """获取缓冲区大小"""
        with self._lock:
            return len(self.buffer)

    def should_flush(self) -> bool:
        """判断是否应该刷新"""
        if len(self.buffer) >= self.batch_size:
            return True
        if time.time() - self.last_flush_time >= self.flush_interval:
            return True
        return False


# 全局缓冲区实例
_buffer_service: Optional[EvaluationBufferService] = None
_buffer_lock = threading.Lock()


def get_buffer_service() -> EvaluationBufferService:
    """获取缓冲区服务单例"""
    global _buffer_service
    if _buffer_service is None:
        with _buffer_lock:
            if _buffer_service is None:
                _buffer_service = EvaluationBufferService(
                    batch_size=100,
                    flush_interval=5.0,
                )
    return _buffer_service


# =====================================================================
# 2. 任务处理函数
# =====================================================================

def _result_to_model(result: TaskResult, trace_id: Optional[str] = None) -> EvaluationResultModel:
    """将 TaskResult 转换为数据库模型"""
    return EvaluationResultModel(
        case_id=result.case_id,
        model_name=result.metadata.get("model_name", "unknown"),
        adapter_name=result.metadata.get("adapter_name", result.task_id[:8]),
        status=result.status.value,
        latency_ms=result.latency_ms,
        response_data={
            "task_id": result.task_id,
            "score": result.score,
            "text": result.response_text,
            "error": result.error_message,
            "trace_id": trace_id or result.trace_id,
            "metadata": result.metadata,
        },
    )


async def _evaluate_domain(domain: str, payload: Dict, llm_client) -> Dict[str, Any]:
    """
    根据领域执行评测

    这里应该调用具体的评测器实现
    """
    # 动态导入避免循环依赖
    from src.domain.evaluators import EVALUATOR_REGISTRY

    evaluator_class = EVALUATOR_REGISTRY.get(domain)
    if not evaluator_class:
        raise ValueError(f"Unknown domain: {domain}")

    evaluator = evaluator_class(client=llm_client)

    # 构建 EvaluationSchema
    request = EvaluationSchema(
        id=payload.get("case_id", str(uuid.uuid4())),
        type=domain,
        payload=payload,
        metadata=payload.get("metadata"),
    )

    result = evaluator.safe_evaluate(request)

    return {
        "is_valid": result.is_valid,
        "score": result.score,
        "text": result.text,
        "metadata": result.metadata,
    }


# =====================================================================
# 3. Celery 任务定义
# =====================================================================

@celery_app.task(
    base=EvalTask,
    bind=True,
    name="src.worker.tasks.eval_case_task",
    max_retries=3,
    default_retry_delay=5,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
)
def eval_case_task(self, case_data: Dict) -> Dict[str, Any]:
    """
    评测任务

    特性:
    - 自动重试 (指数退避)
    - 熔断器保护
    - 分布式锁防止重复
    - 结果缓冲批量写入
    """
    case_id = case_data.get("case_id", "unknown")
    task_id = self.request.id

    logger.info(f"Processing task {task_id}, case {case_id}")

    # 获取 Redis 客户端
    redis_client = get_redis_client()

    # 创建任务处理器
    processor = DistributedTaskProcessor(
        redis_client=redis_client,
        worker_id=self.worker_id,
    )

    # 获取或创建该领域的熔断器
    domain = case_data.get("domain", "general")
    circuit_breaker = global_registry.get_or_create(domain)

    try:
        # 检查熔断器
        if circuit_breaker.is_open:
            logger.warning(f"Circuit breaker open for domain {domain}")
            # 重新抛出让 Celery 重试
            raise Exception(f"Circuit breaker open for domain {domain}")

        # 执行任务处理
        from src.distributed.queue import MessagePriority, QueueMessage

        task_msg = QueueMessage(
            message_id=task_id,
            payload=case_data,
            priority=MessagePriority.NORMAL,
            trace_id=None,
            retry_count=self.request.retries,
        )

        # 使用同步方式运行异步处理
        import asyncio

        def run_async():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(
                    processor.process_task(task_msg, _evaluate_domain)
                )
            finally:
                loop.close()

        result = run_async()

        # 记录熔断器成功
        circuit_breaker._record_success()

        # 写入缓冲区
        model = _result_to_model(result, trace_id=result.trace_id)
        buffer_svc = get_buffer_service()
        buffer_svc.add(model)

        # 检查是否需要刷新
        if buffer_svc.should_flush():
            try:
                buffer_svc.flush()
            except Exception as e:
                logger.error(f"Failed to flush buffer: {e}")

        # 记录指标
        metrics = get_registry()
        counter = metrics.get_metric("eval_tasks_total")
        if counter:
            counter.inc(domain=domain, status=result.status.value)

        return {
            "status": "success",
            "task_id": task_id,
            "case_id": case_id,
            "result_status": result.status.value,
            "score": result.score,
            "latency_ms": result.latency_ms,
            "trace_id": result.trace_id,
        }

    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}", exc_info=True)

        # 记录熔断器失败
        circuit_breaker._record_failure()

        # 更新指标
        metrics = get_registry()
        counter = metrics.get_metric("eval_task_errors_total")
        if counter:
            counter.inc(domain=domain, error_type=type(e).__name__)

        # 重新抛出让 Celery 重试
        raise


@celery_app.task(
    base=EvalTask,
    name="src.worker.tasks.flush_buffer",
    ignore_result=True,
)
def flush_buffer() -> Dict[str, int]:
    """定期刷新缓冲区"""
    buffer_svc = get_buffer_service()
    count = buffer_svc.flush()
    return {"flushed": count}


@celery_app.task(
    base=EvalTask,
    name="src.worker.tasks.get_stats",
)
def get_worker_stats() -> Dict[str, Any]:
    """获取 Worker 统计信息"""
    buffer_svc = get_buffer_service()
    metrics = get_registry()

    return {
        "worker_id": os.getenv("CELERY_WORKER_ID", "unknown"),
        "buffer_size": buffer_svc.get_size(),
        "circuit_breakers": global_registry.all_stats(),
        "metrics": metrics.all_stats(),
    }
