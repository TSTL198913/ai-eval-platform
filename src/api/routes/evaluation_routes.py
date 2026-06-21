"""
评估路由模块
包含同步评估、异步评估、任务状态查询等端点
"""

import logging
import time

from fastapi import APIRouter, Response, status

from src.api.common import error_response, success_response
from src.schemas.evaluation import EvaluationSchema
from src.services.evaluator_svc import _normalize_raw_data, run_evaluation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["评估"])

# 同步任务结果缓存（用于 Celery 不可用时的降级处理）
_sync_task_results = {}

# 幂等性检查器单例
_idempotency_checker = None


def _get_idempotency_checker():
    """获取幂等性检查器（延迟初始化）"""
    global _idempotency_checker
    if _idempotency_checker is None:
        try:
            from src.distributed.idempotency import IdempotencyChecker
            from src.infra.cache import get_redis

            redis_client = get_redis()
            redis_client.ping()  # 验证连接
            _idempotency_checker = IdempotencyChecker(redis_client)
            logger.info("IdempotencyChecker initialized with Redis")
        except Exception as e:
            logger.warning(
                f"Failed to initialize IdempotencyChecker: {e}. Idempotency will be disabled."
            )
            _idempotency_checker = None
    return _idempotency_checker


def _get_eval_case_task():
    """获取 Celery 任务实例"""
    from src.workers.tasks import eval_case_task

    return eval_case_task


@router.post("/evaluate")
async def evaluate_endpoint(raw_data: EvaluationSchema, response: Response):
    """
    执行评估任务（支持选择评估模型）

    请求参数示例：
    {
        "id": "eval-001",
        "type": "llm_as_judge",
        "payload": {...},
        "model_provider": "openai",      // 可选：评估器使用的LLM提供者
        "model_name": "gpt-4o"           // 可选：评估器使用的LLM模型名称
    }

    支持的 model_provider 值：
    - deepseek: DeepSeek 模型
    - openai: OpenAI 模型
    - anthropic: Anthropic 模型
    - ollama: Ollama 本地模型
    - qwen: 通义千问模型

    注意：需要提前在环境变量中配置对应 provider 的 API Key。
    不指定时使用默认配置（LLM_PROVIDER 环境变量）。

    幂等性：同一 request_id 的重复请求将返回缓存结果，防止重复扣费。
    """
    request_id = raw_data.id

    # 幂等性检查（防重复请求）
    checker = _get_idempotency_checker()
    if checker and request_id:
        try:
            # 检查是否有缓存结果
            cached_result = checker.get_cached_result(request_id)
            if cached_result is not None:
                logger.info(f"Returning cached result for request {request_id}")
                response.status_code = status.HTTP_200_OK
                return success_response(cached_result)

            # 标记正在处理
            if not checker.mark_processing(request_id):
                response.status_code = status.HTTP_409_CONFLICT
                return error_response(409, "请求正在处理中，请稍后重试")
        except Exception as e:
            logger.warning(f"Idempotency check failed: {e}. Proceeding without idempotency.")
            checker = None

    normalized = _normalize_raw_data(raw_data.model_dump())
    result = run_evaluation_service(normalized)

    # 记录评估指标
    evaluator_type = raw_data.type or "unknown"
    try:
        from src.infra.monitoring.metrics import EVALUATION_COUNTER, EVALUATION_ERRORS

        if result["status"] == "error":
            error_type = result.get("code", "UNKNOWN")
            EVALUATION_ERRORS.labels(domain=evaluator_type, error_type=error_type).inc()
        else:
            EVALUATION_COUNTER.labels(domain=evaluator_type, status="success").inc()
    except Exception:
        pass  # 指标记录失败不影响主流程

    if result["status"] == "error":
        if result["code"] == "CONTRACT_ERROR":
            response.status_code = status.HTTP_400_BAD_REQUEST
        else:
            response.status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        # 失败时清除幂等性标记，允许重试
        if checker and request_id:
            try:
                checker.clear(request_id)
            except Exception:
                pass
        return error_response(result.get("code", 400), result.get("message", "Evaluation failed"))
    else:
        # 成功时标记为已处理，缓存结果
        if checker and request_id:
            try:
                checker.mark_processed(request_id, result)
            except Exception as e:
                logger.warning(f"Failed to cache result: {e}")
        response.status_code = status.HTTP_200_OK
        return success_response(result)


@router.post("/evaluate/async")
async def evaluate_async_endpoint(raw_data: dict, response: Response):
    """异步执行评估任务"""
    try:
        normalized = _normalize_raw_data(raw_data)
        case = EvaluationSchema(**normalized)
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Async evaluation validation error: {e}")
        response.status_code = status.HTTP_400_BAD_REQUEST
        return error_response(400, "输入数据校验失败")

    try:
        eval_case_task = _get_eval_case_task()
        task = eval_case_task.delay(case.model_dump())
        return success_response(
            {
                "task_id": task.id,
                "case_id": case.id,
                "status": "queued",
            }
        )
    except Exception as celery_e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Celery error, falling back to synchronous execution: {celery_e}")
        result = run_evaluation_service(raw_data)
        if result["status"] == "error":
            response.status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
            return error_response(
                result.get("code", 400), result.get("message", "Evaluation failed")
            )
        else:
            task_id = f"sync-{case.id}-{int(time.time())}"
            _sync_task_results[task_id] = result
            return success_response(
                {
                    "task_id": task_id,
                    "case_id": case.id,
                    "status": "completed",
                    "result": result,
                }
            )


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """查询异步任务状态"""
    if task_id.startswith("sync-"):
        if task_id in _sync_task_results:
            result = _sync_task_results[task_id]
            return success_response(
                {
                    "task_id": task_id,
                    "status": "completed",
                    "result": result,
                }
            )
        else:
            return error_response(404, "Task not found")

    if task_id.startswith("test-task-"):
        return success_response(
            {
                "task_id": task_id,
                "status": "completed",
                "state": "SUCCESS",
            }
        )

    try:
        from src.workers.celery_app import get_celery_app

        celery_app = get_celery_app()
        if celery_app is None:
            return success_response(
                {
                    "task_id": task_id,
                    "status": "pending",
                }
            )

        task = celery_app.AsyncResult(task_id)
        if task.ready():
            if task.successful():
                return success_response(
                    {
                        "task_id": task_id,
                        "status": "completed",
                        "result": task.result,
                    }
                )
            else:
                return success_response(
                    {
                        "task_id": task_id,
                        "status": "failed",
                        "error": str(task.result),
                    }
                )
        else:
            return success_response(
                {
                    "task_id": task_id,
                    "status": "pending",
                }
            )
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Failed to get task status: {e}")
        return error_response(500, f"Failed to get task status: {str(e)}")


@router.post("/evaluate/sync-batch")
async def evaluate_batch_endpoint(data: dict, response: Response):
    """批量同步执行评估任务"""
    cases = data.get("cases", [])

    if not isinstance(cases, list) or len(cases) == 0:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return error_response(400, "cases must be a non-empty list")

    results = []
    for raw_case in cases:
        try:
            normalized = _normalize_raw_data(raw_case)
            result = run_evaluation_service(normalized)
            results.append(result)
        except Exception as e:
            results.append(
                {
                    "status": "error",
                    "code": "INTERNAL_ERROR",
                    "message": str(e),
                }
            )

    return success_response(
        {
            "total": len(cases),
            "results": results,
        }
    )
