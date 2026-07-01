import logging
from functools import wraps
from typing import Any, Optional

from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.models.llm_factory import create_llm_client
from src.engine import EvaluationEngine
from src.exceptions import BasePlatformError, DomainLogicError
from src.infra.db.repository import EvaluationRepository
from src.schemas.evaluation import EvaluationSchema


def _get_evaluator_registry():
    from src.domain.evaluators import EVALUATOR_REGISTRY

    registry = EvaluatorFactory._registry
    if not registry and EVALUATOR_REGISTRY:
        return EVALUATOR_REGISTRY
    return registry


def get_idempotency_service() -> Any | None:
    try:
        from src.distributed.idempotency import IdempotencyChecker
        from src.infra.cache import get_redis

        redis_client = get_redis()
        redis_client.ping()
        return IdempotencyChecker(redis_client)
    except Exception as e:
        logging.warning(f"Failed to initialize IdempotencyService: {e}")
        return None


def get_eval_task() -> Any:
    try:
        from src.workers.tasks import eval_case_task

        return eval_case_task
    except ImportError:
        logging.warning("Celery workers not available, async tasks will use sync fallback")
        return None


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
            "payload": {
                k: v
                for k, v in raw_data.items()
                if k not in ["id", "type", "metadata", "model_provider", "model_name"]
            },
            "metadata": raw_data.get("metadata", {}),
            "model_provider": raw_data.get("model_provider"),
            "model_name": raw_data.get("model_name"),
        }
    return raw_data


class EvaluatorService:
    def __init__(
        self,
        repository: Optional[EvaluationRepository] = None,
        engine: Optional[EvaluationEngine] = None,
    ):
        self.repository = repository or EvaluationRepository()
        self.engine = engine

    def run_evaluation(self, raw_data: dict[str, Any], client=None) -> dict[str, Any]:
        raw_data = _normalize_raw_data(raw_data)
        case = EvaluationSchema(**raw_data)

        registry = _get_evaluator_registry()
        if case.type not in registry:
            raise DomainLogicError(f"No adapter found for type: {case.type}")

        routing_decision = None

        if client is not None:
            llm_client = client
        elif case.model_provider:
            from src.domain.models.llm_factory import load_config

            loaded_config = load_config(case.model_provider)
            if case.model_name:
                loaded_config = loaded_config.model_copy(update={"model_name": case.model_name})
            llm_client = create_llm_client(provider=case.model_provider, config=loaded_config)
        else:
            from src.domain.model_routing import model_router

            llm_client, routing_decision = model_router.create_llm_client(case.type, case.payload)

        engine = self.engine or EvaluationEngine(llm_client)
        result = engine.run(case)

        persist_success = True
        persist_error = None
        try:
            db_id = self.repository.save(result)
            logging.info(
                f"评估结果已持久化: id={db_id}, case_id={result.case_id}, status={result.status.value}"
            )
        except Exception as e:
            persist_success = False
            persist_error = str(e)
            logging.error(f"评估结果持久化失败: {e}", exc_info=True)

        status = "success" if result.status.value != "error" else "error"
        code = None
        message = None

        if result.status.value == "error":
            code = "EVALUATION_ERROR"
            message = result.error_message or "Evaluation failed"

        return {
            "status": status,
            "code": code,
            "message": message,
            "record_id": case.id,
            "evaluation_status": result.status.value,
            "latency_ms": result.latency_ms,
            "data": result.response.model_dump() if result.response else None,
            "routing": routing_decision,
            "persist": persist_success,
            "persist_error": persist_error,
        }


@service_exception_handler
def run_evaluation_service(raw_data: dict[str, Any], client=None) -> dict[str, Any]:
    service = EvaluatorService()
    return service.run_evaluation(raw_data, client)