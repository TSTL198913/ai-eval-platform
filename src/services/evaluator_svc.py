import logging
from functools import wraps
from typing import Any

from src.domain.evaluators import EVALUATOR_REGISTRY
from src.domain.models.llm_factory import create_llm_client
from src.engine import EvaluationEngine
from src.exceptions import BasePlatformError, DomainLogicError
from src.infra.db.repository import EvaluationRepository
from src.schemas.evaluation import EvaluationSchema

_repository = EvaluationRepository()


def service_exception_handler(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BasePlatformError as e:
            logging.error(f"捕获到平台业务异常 [{e.code}]: {e.message}")
            return {"status": "error", "code": e.code, "message": e.message}
        except Exception as e:
            if "ValidationError" in type(e).__name__:
                return {"status": "error", "code": "CONTRACT_ERROR", "message": str(e)}
            logging.error(f"系统内部错误: {type(e).__name__} - {str(e)}", exc_info=True)
            return {
                "status": "error",
                "code": "INTERNAL_ERROR",
                "message": "系统内部发生不可预知的错误",
            }

    return wrapper


def _normalize_raw_data(raw_data: dict[str, Any]) -> dict[str, Any]:
    if "payload" not in raw_data:
        return {
            "id": raw_data.get("id", "unknown"),
            "type": raw_data.get("type"),
            "payload": {k: v for k, v in raw_data.items() if k not in ["id", "type", "metadata"]},
            "metadata": raw_data.get("metadata", {}),
        }
    return raw_data


@service_exception_handler
def run_evaluation_service(raw_data: dict[str, Any], client=None) -> dict[str, Any]:
    raw_data = _normalize_raw_data(raw_data)
    case = EvaluationSchema(**raw_data)

    if case.type not in EVALUATOR_REGISTRY:
        raise DomainLogicError(f"No adapter found for type: {case.type}")

    engine = EvaluationEngine(create_llm_client(client=client))
    result = engine.run(case)

    # 使用 Repository 持久化评估结果
    try:
        db_id = _repository.save(result)
        logging.info(
            f"评估结果已持久化: id={db_id}, case_id={result.case_id}, status={result.status.value}"
        )
    except Exception as e:
        logging.error(f"评估结果持久化失败: {e}", exc_info=True)

    return {
        "status": "success",
        "record_id": case.id,
        "evaluation_status": result.status.value,
        "latency_ms": result.latency_ms,
        "data": result.response,
    }
