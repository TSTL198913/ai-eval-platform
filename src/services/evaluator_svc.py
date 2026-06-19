import logging
from functools import wraps
from typing import Any

from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.models.llm_factory import create_llm_client

# 动态获取评估器注册表，避免与 EvaluatorFactory._registry 不同步
def _get_evaluator_registry():
    from src.domain.evaluators import EVALUATOR_REGISTRY
    # 优先使用 EvaluatorFactory 的实时注册表，若为空则回退到模块级变量
    registry = EvaluatorFactory._registry
    if not registry and EVALUATOR_REGISTRY:
        return EVALUATOR_REGISTRY
    return registry

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
            "payload": {k: v for k, v in raw_data.items() if k not in ["id", "type", "metadata", "model_provider", "model_name"]},
            "metadata": raw_data.get("metadata", {}),
            "model_provider": raw_data.get("model_provider"),
            "model_name": raw_data.get("model_name"),
        }
    return raw_data


@service_exception_handler
def run_evaluation_service(raw_data: dict[str, Any], client=None) -> dict[str, Any]:
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

    engine = EvaluationEngine(llm_client)
    result = engine.run(case)

    persist_success = True
    persist_error = None
    try:
        db_id = _repository.save(result)
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
