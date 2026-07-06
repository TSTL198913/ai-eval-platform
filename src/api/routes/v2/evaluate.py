"""
v2 评估路由 - 明确区分推理和评估阶段

设计原则：
1. 两阶段调用：先推理（生成 actual_output），再评估
2. 单步便捷路径：支持 evaluate_mode=ONLINE 自动完成两阶段
3. 显式模型配置：支持不同模型进行推理和评估
4. 独立持久化：评估结果自动持久化
5. 工业级特性：幂等性、指标监控、统一错误处理
"""

import logging
from functools import wraps
from typing import Optional

from fastapi import APIRouter
from fastapi import Body
from fastapi import Response
from fastapi import status

from src.api.common import error_response
from src.api.common import success_response
from src.domain.services.client_factory_service import ClientFactoryService
from src.domain.services.inference_service import InferenceService
from src.domain.services.persistence_service import PersistenceService
from src.exceptions import BasePlatformError
from src.services.evaluator_svc import EvaluatorService
from src.services.evaluator_svc import get_idempotency_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["评估 v2"])

_idempotency_checker = None


def _get_idempotency_checker():
    global _idempotency_checker
    if _idempotency_checker is None:
        try:
            _idempotency_checker = get_idempotency_service()
            logger.info("IdempotencyChecker initialized for v2 API")
        except Exception as e:
            logger.warning(f"Failed to initialize IdempotencyChecker: {e}")
            _idempotency_checker = None
    return _idempotency_checker


def v2_exception_handler(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except BasePlatformError as e:
            logger.error(f"平台业务异常 [{e.code}]: {e.message}")
            return error_response(e.code, e.message)
        except Exception as e:
            logger.error(f"系统内部错误: {type(e).__name__} - {str(e)}", exc_info=True)
            return error_response(500, "系统内部发生不可预知的错误")

    return wrapper


def _record_metrics(evaluator_type: str, success: bool, error_type: str = None):
    try:
        from src.infra.monitoring.metrics import EVALUATION_COUNTER
        from src.infra.monitoring.metrics import EVALUATION_ERRORS

        if success:
            EVALUATION_COUNTER.labels(domain=evaluator_type, status="success").inc()
        else:
            EVALUATION_ERRORS.labels(domain=evaluator_type, error_type=error_type or "UNKNOWN").inc()
    except Exception as e:
        logger.warning(f"Failed to record metrics: {e}")


@router.post("/inference")
@v2_exception_handler
async def inference_endpoint(
    prompt: str = Body(..., embed=True),
    model_provider: Optional[str] = Body(None, embed=True),
    model_name: Optional[str] = Body(None, embed=True),
    response: Response = None,
):
    """
    推理端点：生成 actual_output
    
    使用指定的 LLM 模型生成推理结果，用于后续评估。
    
    Args:
        prompt: 输入提示
        model_provider: 推理模型提供者（deepseek/openai/anthropic/ollama/qwen）
        model_name: 推理模型名称
        
    Returns:
        {
            "code": 0,
            "message": "success",
            "data": {
                "output": "生成的文本",
                "model_provider": "deepseek",
                "model_name": "deepseek-chat"
            }
        }
    """
    client = ClientFactoryService.create_eval_client(
        model_provider, model_name, "inference", {"prompt": prompt}
    )[0]

    inference_service = InferenceService(client)
    output = inference_service.generate(prompt)

    _record_metrics("inference", success=True)

    return success_response(
        {
            "output": output,
            "model_provider": model_provider or client.config.provider,
            "model_name": model_name or client.config.model_name,
        }
    )


@router.post("/evaluate")
@v2_exception_handler
async def evaluate_endpoint(
    type: str = Body(..., embed=True),
    payload: dict = Body(..., embed=True),
    id: Optional[str] = Body(None, embed=True),
    evaluate_mode: str = Body("offline", embed=True),
    model_provider: Optional[str] = Body(None, embed=True),
    model_name: Optional[str] = Body(None, embed=True),
    inference_model_provider: Optional[str] = Body(None, embed=True),
    inference_model_name: Optional[str] = Body(None, embed=True),
    metadata: Optional[dict] = Body(None, embed=True),
    response: Response = None,
):
    """
    评估端点：执行评估（支持两阶段和单步模式）
    
    两阶段模式（推荐）：
    1. 先调用 POST /api/v2/inference 生成 actual_output
    2. 将 actual_output 放入 payload 中调用此端点
    
    单步模式（便捷）：
    设置 evaluate_mode=online，系统自动完成推理和评估
    
    Args:
        type: 评估类型（qa/code/general/semantic/llm_as_judge等）
        payload: 评估数据，必须包含 actual_output（offline模式）或 prompt（online模式）
        id: 请求ID（可选，用于幂等性检查）
        evaluate_mode: 评估模式（offline/online）
        model_provider: 评估模型提供者
        model_name: 评估模型名称
        inference_model_provider: 推理模型提供者（online模式）
        inference_model_name: 推理模型名称（online模式）
        metadata: 元数据（可选）
        
    Returns:
        {
            "code": 0,
            "message": "success",
            "data": {
                "record_id": "eval-001",
                "evaluation_status": "passed",
                "score": 0.95,
                "latency_ms": 1234,
                "persist": true,
                ...
            }
        }
    """
    checker = _get_idempotency_checker()
    request_id = id

    if checker and request_id:
        try:
            cached_result = checker.get_cached_result(request_id)
            if cached_result is not None:
                logger.info(f"Returning cached result for request {request_id}")
                response.status_code = status.HTTP_200_OK
                _record_metrics(type, success=True)
                return success_response(cached_result)

            if not checker.mark_processing(request_id):
                response.status_code = status.HTTP_409_CONFLICT
                _record_metrics(type, success=False, error_type="CONFLICT")
                return error_response(409, "请求正在处理中，请稍后重试")
        except Exception as e:
            logger.warning(f"Idempotency check failed: {e}")
            checker = None

    eval_client, inference_client, _ = ClientFactoryService.create_clients(
        model_provider, model_name, inference_model_provider, inference_model_name, type, payload
    )

    raw_data = {
        "id": id,
        "type": type,
        "evaluate_mode": evaluate_mode,
        "payload": payload,
        "metadata": metadata,
        "model_provider": model_provider,
        "model_name": model_name,
        "inference_model_provider": inference_model_provider,
        "inference_model_name": inference_model_name,
    }

    evaluator_service = EvaluatorService()
    service_response = evaluator_service.run_evaluation(
        raw_data,
        client=eval_client,
        inference_client=inference_client,
    )

    eval_result = service_response.api_response

    persist_result = {"success": False, "error": None}
    if eval_result["status"] == "success":
        try:
            domain_result = service_response.domain_result
            persistence_service = PersistenceService()
            persist_result = persistence_service.save_evaluation(domain_result)
        except Exception as e:
            logger.warning(f"持久化失败，但评估成功: {e}")

    eval_result["persist"] = persist_result["success"]
    eval_result["persist_error"] = persist_result["error"]

    if eval_result["status"] == "error":
        error_code = eval_result.get("code", 400)
        error_message = eval_result.get("message", "Evaluation failed")

        _record_metrics(type, success=False, error_type=error_code)

        if checker and request_id:
            try:
                checker.clear(request_id)
            except Exception as e:
                logger.warning(f"Failed to clear idempotency key: {e}")

        if error_code == "CONTRACT_ERROR":
            response.status_code = status.HTTP_400_BAD_REQUEST
        else:
            response.status_code = status.HTTP_422_UNPROCESSABLE_ENTITY

        return error_response(error_code, error_message)

    _record_metrics(type, success=True)

    if checker and request_id:
        try:
            checker.mark_processed(request_id, eval_result)
        except Exception as e:
            logger.warning(f"Failed to cache result: {e}")

    response.status_code = status.HTTP_200_OK
    return success_response(eval_result)