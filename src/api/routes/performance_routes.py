"""
模型性能分析 API

提供模型性能总览、详情、对比等接口。
"""

from typing import Any

from fastapi import APIRouter, Depends

from src.api.common import error_response, success_response
from src.api.dependencies import PermissionDependency
from src.infra.security import Permission

router = APIRouter(prefix="/api/v1/models/performance", tags=["模型性能分析"])


@router.get("", response_model=dict[str, Any])
async def get_performance_overview(
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_MODEL_VERSIONS)),
) -> dict[str, Any]:
    """
    获取性能总览

    需要 MANAGE_MODEL_VERSIONS 权限。

    返回所有模型的性能概览数据。
    """
    try:
        from src.domain.model_performance_analyzer import ModelPerformanceAnalyzer

        analyzer = ModelPerformanceAnalyzer()
        overview = analyzer.get_overview()

        return success_response(overview)
    except Exception as e:
        return error_response(500, f"获取性能总览失败: {str(e)}")


@router.get("/{model_name}", response_model=dict[str, Any])
async def get_model_performance(
    model_name: str,
    period: str = "daily",
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_MODEL_VERSIONS)),
) -> dict[str, Any]:
    """
    获取模型性能详情

    需要 MANAGE_MODEL_VERSIONS 权限。

    Args:
        period: 时间周期: hourly, daily, weekly, monthly
    """
    try:
        from src.domain.model_performance_analyzer import ModelPerformanceAnalyzer

        analyzer = ModelPerformanceAnalyzer()
        performance = analyzer.get_model_performance(model_name, period=period)

        if not performance:
            return error_response(404, f"模型 '{model_name}' 暂无性能数据")

        return success_response(performance)
    except Exception as e:
        return error_response(500, f"获取模型性能失败: {str(e)}")


@router.post("/compare")
async def compare_performance(
    request: dict,
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_MODEL_VERSIONS)),
) -> dict[str, Any]:
    """
    性能对比

    需要 MANAGE_MODEL_VERSIONS 权限。

    对比多个模型的性能指标。
    """
    try:
        from src.domain.model_performance_analyzer import ModelPerformanceAnalyzer

        analyzer = ModelPerformanceAnalyzer()
        model_names = request.get("model_names", [])

        if not model_names:
            return error_response(400, "model_names 必填")

        comparison = analyzer.compare_models(model_names)

        return success_response(comparison)
    except Exception as e:
        return error_response(500, f"性能对比失败: {str(e)}")


@router.get("/{model_name}/metrics")
async def get_model_metrics(
    model_name: str,
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_MODEL_VERSIONS)),
) -> dict[str, Any]:
    """
    获取模型详细指标

    需要 MANAGE_MODEL_VERSIONS 权限。

    返回模型的各项性能指标，包括延迟、吞吐量、准确率等。
    """
    try:
        from src.domain.model_performance_analyzer import ModelPerformanceAnalyzer

        analyzer = ModelPerformanceAnalyzer()
        metrics = analyzer.get_model_metrics(model_name)

        if not metrics:
            return error_response(404, f"模型 '{model_name}' 暂无指标数据")

        return success_response(metrics)
    except Exception as e:
        return error_response(500, f"获取模型指标失败: {str(e)}")


@router.get("/{model_name}/trends")
async def get_performance_trends(
    model_name: str,
    period: str = "daily",
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_MODEL_VERSIONS)),
) -> dict[str, Any]:
    """
    获取性能趋势

    需要 MANAGE_MODEL_VERSIONS 权限。

    返回模型性能随时间的变化趋势。
    """
    try:
        from src.domain.model_performance_analyzer import ModelPerformanceAnalyzer

        analyzer = ModelPerformanceAnalyzer()
        trends = analyzer.get_trends(model_name, period=period)

        return success_response(trends)
    except Exception as e:
        return error_response(500, f"获取性能趋势失败: {str(e)}")


@router.get("/top-performers")
async def get_top_performers(
    metric: str = "accuracy",
    limit: int = 10,
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_MODEL_VERSIONS)),
) -> dict[str, Any]:
    """
    获取性能最佳的模型

    需要 MANAGE_MODEL_VERSIONS 权限。

    Args:
        metric: 排序指标: accuracy, latency, throughput, cost_efficiency
    """
    try:
        from src.domain.model_performance_analyzer import ModelPerformanceAnalyzer

        analyzer = ModelPerformanceAnalyzer()
        top_models = analyzer.get_top_performers(metric=metric, limit=limit)

        return success_response({"top_models": top_models})
    except Exception as e:
        return error_response(500, f"获取最佳模型失败: {str(e)}")
