import time
from typing import Dict

from celery import Task

from src.infra.db.models import EvaluationResultModel
from src.infra.db.session import SessionLocal
from src.workers.celery_app import celery_app


class EvaluationBufferService:
    """业务逻辑核心：负责数据缓冲与落盘，脱离框架独立运行"""

    def __init__(self):
        self.buffer = []
        self.batch_size = 1000
        self.last_flush_time = time.time()

    def add(self, item: EvaluationResultModel):
        self.buffer.append(item)
        return len(self.buffer)

    def flush(self, db_session=None):
        if not self.buffer:
            return

        # 依赖注入：测试环境可传入 db_session，生产环境自动创建
        db = db_session if db_session is not None else SessionLocal()
        is_external = db_session is not None

        try:
            db.bulk_save_objects(self.buffer)
            db.commit()
            self.buffer.clear()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            if not is_external:
                db.close()
            self.last_flush_time = time.time()


# 全局单例，确保逻辑层内存唯一
buffer_service = EvaluationBufferService()


class WindowsUltimateSoloTask(Task):
    """调度适配层：仅负责任务触发"""

    def flush(self, db_session=None):
        return buffer_service.flush(db_session)


@celery_app.task(base=WindowsUltimateSoloTask, bind=True)
def eval_case_task(self, case_data: Dict):
    result = EvaluationResultModel(case_id=case_data.get("id", "unknown"), status=1)
    buffer_service.add(result)
    # 策略执行
    if len(buffer_service.buffer) >= buffer_service.batch_size:
        buffer_service.flush()
    return {"status": "success"}
