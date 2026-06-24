"""
在线评估监控 API

提供在线采样状态、统计信息等接口。
"""

from typing import Any

from fastapi import APIRouter, Depends

from src.api.common import error_response, success_response
from src.api.dependencies import PermissionDependency
from src.infra.security import Permission

router = APIRouter(prefix="/api/v1/online", tags=["在线评估"])


@router.post("/sampling/start")
async def start_sampling(
    request: dict,
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_MODEL_VERSIONS)),
) -> dict[str, Any]:
    """
    开始采样

    需要 MANAGE_MODEL_VERSIONS 权限。

    开始从生产环境采样请求进行评估。
    """
    try:
        from src.domain.online.evaluator import ProductionSampler

        sampler = ProductionSampler()
        result = sampler.start_sampling(
            model_name=request.get("model_name"),
            sample_rate=request.get("sample_rate", 0.01),
            max_samples=request.get("max_samples", 100),
        )

        return success_response(
            {
                "status": "started",
                "model_name": request.get("model_name"),
                "sample_rate": request.get("sample_rate", 0.01),
                "message": result.get("message", "采样已开始"),
            }
        )
    except Exception as e:
        return error_response(500, f"启动采样失败: {str(e)}")


@router.post("/sampling/stop")
async def stop_sampling(
    request: dict,
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_MODEL_VERSIONS)),
) -> dict[str, Any]:
    """
    停止采样

    需要 MANAGE_MODEL_VERSIONS 权限。
    """
    try:
        from src.domain.online.evaluator import ProductionSampler

        sampler = ProductionSampler()
        result = sampler.stop_sampling(model_name=request.get("model_name"))

        return success_response(
            {
                "status": "stopped",
                "model_name": request.get("model_name"),
                "message": result.get("message", "采样已停止"),
            }
        )
    except Exception as e:
        return error_response(500, f"停止采样失败: {str(e)}")


@router.get("/stats")
async def get_sampling_stats(
    model_name: str | None = None,
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_MODEL_VERSIONS)),
) -> dict[str, Any]:
    """
    获取采样统计

    需要 MANAGE_MODEL_VERSIONS 权限。
    """
    try:
        from src.domain.online.evaluator import OnlineEvaluator

        evaluator = OnlineEvaluator()
        stats = evaluator.get_stats(model_name=model_name)

        return success_response(stats)
    except Exception as e:
        return error_response(500, f"获取采样统计失败: {str(e)}")


@router.get("/evaluations")
async def get_online_evaluations(
    model_name: str | None = None,
    limit: int = 50,
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_MODEL_VERSIONS)),
) -> dict[str, Any]:
    """
    获取在线评估结果

    需要 MANAGE_MODEL_VERSIONS 权限。
    """
    try:
        from src.domain.online.evaluator import OnlineEvaluator

        evaluator = OnlineEvaluator()
        evaluations = evaluator.get_evaluations(model_name=model_name, limit=limit)

        return success_response(
            {
                "evaluations": evaluations,
                "total": len(evaluations),
            }
        )
    except Exception as e:
        return error_response(500, f"获取评估结果失败: {str(e)}")


@router.get("/health")
async def get_online_health(
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_MODEL_VERSIONS)),
) -> dict[str, Any]:
    """
    获取在线评估健康状态

    需要 MANAGE_MODEL_VERSIONS 权限。
    """
    try:
        from src.domain.online.evaluator import OnlineEvaluator

        evaluator = OnlineEvaluator()
        health = evaluator.get_health()

        return success_response(health)
    except Exception as e:
        return error_response(500, f"获取健康状态失败: {str(e)}")


@router.get("/quality")
async def get_online_quality(
    model_name: str | None = None,
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_MODEL_VERSIONS)),
) -> dict[str, Any]:
    """
    获取在线质量评分

    需要 MANAGE_MODEL_VERSIONS 权限。

    返回模型在生产环境中的实时质量评分。
    """
    try:
        from src.domain.online.evaluator import OnlineEvaluator

        evaluator = OnlineEvaluator()
        quality = evaluator.get_quality_score(model_name=model_name)

        return success_response(quality)
    except Exception as e:
        return error_response(500, f"获取质量评分失败: {str(e)}")
