import logging
from functools import wraps
from typing import Any
from typing import Optional

from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.engine import EvaluationEngine
from src.exceptions import BasePlatformError
from src.exceptions import DomainLogicError
from src.schemas.evaluation import EvaluationSchema
from src.schemas.schemas import EvaluationResult

logger = logging.getLogger(__name__)


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
        logger.warning(f"Failed to initialize IdempotencyService: {e}")
        return None


def get_eval_task() -> Any:
    try:
        from src.workers.tasks import eval_case_task

        return eval_case_task
    except ImportError:
        logger.warning("Celery workers not available, async tasks will use sync fallback")
        return None


def service_exception_handler(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BasePlatformError as e:
            logger.error(f"捕获到平台业务异常 [{e.code}]: {e.message}")
            return {"status": "error", "code": e.code, "message": e.message}
        except Exception as e:
            if "ValidationError" in type(e).__name__:
                return {"status": "error", "code": "CONTRACT_ERROR", "message": str(e)}
            logger.error(f"系统内部错误: {type(e).__name__} - {str(e)}", exc_info=True)
            return {
                "status": "error",
                "code": "INTERNAL_ERROR",
                "message": "系统内部发生不可预知的错误",
            }

    return wrapper


def _normalize_raw_data(raw_data: dict[str, Any]) -> dict[str, Any]:
    result = {
        "id": raw_data.get("id") if raw_data.get("id") is not None else "unknown",
        "type": raw_data.get("type"),
        "evaluate_mode": raw_data.get("evaluate_mode", "offline"),
        "payload": raw_data.get("payload", {}),
        "metadata": raw_data.get("metadata", {}),
        "model_provider": raw_data.get("model_provider"),
        "model_name": raw_data.get("model_name"),
        "inference_model_provider": raw_data.get("inference_model_provider"),
        "inference_model_name": raw_data.get("inference_model_name"),
    }
    if "payload" not in raw_data:
        result["payload"] = {
            k: v
            for k, v in raw_data.items()
            if k not in ["id", "type", "metadata", "model_provider", "model_name", 
                          "inference_model_provider", "inference_model_name", "evaluate_mode"]
        }
    return result


class EvaluationServiceResponse:
    """评估服务响应：明确分离 API 响应和领域结果"""

    def __init__(self, api_response: dict, domain_result):
        self.api_response = api_response
        self.domain_result = domain_result


class EvaluatorService:
    """评估服务：专注于评估执行，不负责客户端创建和持久化"""

    def __init__(self, engine: Optional[EvaluationEngine] = None):
        self.engine = engine

    def run_evaluation(self, raw_data: dict[str, Any], client=None, inference_client=None) -> EvaluationServiceResponse:
        """执行评估（精简版）
        
        Args:
            raw_data: 评估请求数据
            client: 评估器使用的LLM客户端（由外部注入）
            inference_client: 推理使用的LLM客户端（由外部注入）
            
        Returns:
            EvaluationServiceResponse: 评估服务响应，包含 API 响应和领域结果
        """
        raw_data = _normalize_raw_data(raw_data)
        case = EvaluationSchema(**raw_data)

        registry = _get_evaluator_registry()
        if case.type not in registry:
            raise DomainLogicError(f"No adapter found for type: {case.type}")

        engine = self.engine or EvaluationEngine(client, inference_client=inference_client)
        result = engine.run(case)

        return self._build_api_response(case, result)

    def run_batch_evaluation(self, raw_data_list: list[dict[str, Any]], client=None, inference_client=None) -> list[EvaluationServiceResponse]:
        """批量执行评估
        
        Args:
            raw_data_list: 评估请求数据列表
            client: 评估器使用的LLM客户端（由外部注入）
            inference_client: 推理使用的LLM客户端（由外部注入）
            
        Returns:
            评估服务响应列表
        """
        cases = []
        registry = _get_evaluator_registry()
        
        for raw_data in raw_data_list:
            try:
                normalized = _normalize_raw_data(raw_data)
                case = EvaluationSchema(**normalized)
                if case.type not in registry:
                    continue
                cases.append(case)
            except Exception as e:
                logger.error(f"批量评估请求构建失败: {e}")
                continue

        engine = self.engine or EvaluationEngine(client, inference_client=inference_client)
        results = engine.run_batch(cases)

        responses = []
        for case, result in zip(cases, results):
            responses.append(self._build_api_response(case, result))
            
        return responses

    def _build_api_response(self, case: EvaluationSchema, result: EvaluationResult) -> EvaluationServiceResponse:
        """构建API响应"""
        status = "success" if result.status.value != "error" else "error"
        code = None
        message = None

        if result.status.value == "error":
            code = "EVALUATION_ERROR"
            message = result.error_message or "Evaluation failed"

        api_response = {
            "status": status,
            "code": code,
            "message": message,
            "record_id": case.id,
            "evaluation_status": result.status.value,
            "latency_ms": result.latency_ms,
            "data": result.response.model_dump() if result.response else None,
        }

        return EvaluationServiceResponse(api_response, result)


@service_exception_handler
def run_evaluation_service(raw_data: dict[str, Any], client=None) -> dict[str, Any]:
    """
    向后兼容的评估服务入口（v1 API 使用）
    
    保留原有功能：自动创建客户端和持久化
    新代码应直接使用 EvaluatorService.run_evaluation()
    """
    raw_data = _normalize_raw_data(raw_data)
    case = EvaluationSchema(**raw_data)

    registry = _get_evaluator_registry()
    if case.type not in registry:
        raise DomainLogicError(f"No adapter found for type: {case.type}")

    from src.domain.models.llm_factory import create_llm_client

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

    inference_client = None
    if case.inference_model_provider:
        from src.domain.models.llm_factory import load_config

        inference_config = load_config(case.inference_model_provider)
        if case.inference_model_name:
            inference_config = inference_config.model_copy(update={"model_name": case.inference_model_name})
        inference_client = create_llm_client(provider=case.inference_model_provider, config=inference_config)

    engine = EvaluationEngine(llm_client, inference_client=inference_client)
    result = engine.run(case)

    persist_success = True
    persist_error = None
    try:
        from src.domain.services.persistence_service import PersistenceService

        persistence_service = PersistenceService()
        persist_result = persistence_service.save_evaluation(result)
        persist_success = persist_result["success"]
        persist_error = persist_result["error"]
    except Exception as e:
        persist_success = False
        persist_error = str(e)
        logger.error(f"评估结果持久化失败: {e}", exc_info=True)

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