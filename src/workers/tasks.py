import threading
import time

from celery import Task

from src.domain.models.llm_factory import create_llm_client
from src.engine import EvaluationEngine
from src.infra.db.models import EvaluationResultModel
from src.infra.db.session import SessionLocal
from src.schemas.evaluation import EvaluationSchema
from src.schemas.schemas import EvaluationResult
from src.workers.celery_app import celery_app


class EvaluationBufferService:
    """负责评测结果缓冲与批量落盘。"""

    def __init__(self):
        self.buffer = []
        self.batch_size = 1000
        self.last_flush_time = time.time()
        self._lock = threading.Lock()

    def add(self, item: EvaluationResultModel) -> int:
        with self._lock:
            self.buffer.append(item)
            return len(self.buffer)

    def flush(self, db_session=None):
        with self._lock:
            if not self.buffer:
                return
            batch = list(self.buffer)
            self.buffer = []

        db = db_session if db_session is not None else SessionLocal()
        is_external = db_session is not None

        try:
            db.bulk_save_objects(batch)
            db.commit()
        except Exception:
            db.rollback()
            with self._lock:
                self.buffer = batch + self.buffer
            raise
        finally:
            if not is_external:
                db.close()
            self.last_flush_time = time.time()


buffer_service = EvaluationBufferService()


class WindowsUltimateSoloTask(Task):
    def flush(self, db_session=None):
        return buffer_service.flush(db_session)


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
    case = EvaluationSchema(**case_data)
    engine = EvaluationEngine(create_llm_client())
    result = engine.run(case)

    db_record = _result_to_model(result)
    count = buffer_service.add(db_record)
    if count >= buffer_service.batch_size:
        buffer_service.flush()

    return {
        "status": "success",
        "case_id": case.id,
        "evaluation_status": result.status.value,
        "latency_ms": result.latency_ms,
    }
