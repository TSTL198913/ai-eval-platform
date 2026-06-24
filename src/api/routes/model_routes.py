"""模型管理路由模块

提供模型列表查询、模型对比评测、成本指标查询、版本管理等API端点。
"""

import logging

from fastapi import APIRouter, Depends

from src.api.common import error_response, success_response
from src.api.dependencies import PermissionDependency
from src.infra.security import Permission

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1", tags=["模型管理"])


@router.get("/models")
async def get_models():
    """获取所有可用模型列表"""
    try:
        from src.domain.models.llm_factory import ModelRegistry, load_config

        models = []
        for provider in ModelRegistry.list_providers():
            try:
                config = load_config(provider)
                models.append(
                    {
                        "id": f"{provider}-{config.model_name}",
                        "name": config.model_name,
                        "provider": provider,
                        "provider_name": provider.capitalize(),
                        "status": "available",
                    }
                )
            except Exception:
                models.append(
                    {
                        "id": provider,
                        "name": provider,
                        "provider": provider,
                        "provider_name": provider.capitalize(),
                        "status": "config_required",
                    }
                )

        return success_response(models)
    except Exception as e:
        logger.error(f"Failed to get models: {e}")
        return error_response(500, "获取模型列表失败")


@router.post("/models/compare")
async def compare_models(request_data: dict):
    """模型对比评测（演示端点 - 返回模拟数据）

    注意：此端点为演示目的，返回模拟数据。
    生产环境应接入真实的 benchmark 评估流程。
    """
    try:
        models = request_data.get("models", [])
        datasets = request_data.get("datasets", ["mmlu", "gsm8k"])

        if not models:
            return error_response(400, "At least one model is required")

        results = []
        for model_info in models:
            provider = model_info.get("provider", "")
            model_name = model_info.get("name", "")

            try:
                model_results = {
                    "model": model_name,
                    "provider": provider,
                    "datasets": {},
                    "mean_accuracy": 0.0,
                    "mean_latency_ms": 0.0,
                    "total_cost_usd": 0.0,
                    "warning": "此为演示数据，非真实评测结果",
                }

                total_accuracy = 0.0
                total_latency = 0.0
                total_cost = 0.0
                count = 0

                for dataset in datasets:
                    sample_count = min(request_data.get("sample_count", 5), 20)

                    if dataset == "mmlu":
                        model_results["datasets"]["mmlu"] = {
                            "accuracy": 0.75 + (0.05 * count),
                            "samples": sample_count,
                            "latency_ms": 800 + (100 * count),
                            "is_simulated": True,
                        }
                    elif dataset == "gsm8k":
                        model_results["datasets"]["gsm8k"] = {
                            "accuracy": 0.80 + (0.03 * count),
                            "samples": sample_count,
                            "latency_ms": 1200 + (150 * count),
                            "is_simulated": True,
                        }
                    elif dataset == "human_eval":
                        model_results["datasets"]["human_eval"] = {
                            "accuracy": 0.65 + (0.04 * count),
                            "samples": sample_count,
                            "latency_ms": 1500 + (200 * count),
                            "is_simulated": True,
                        }

                    dataset_result = model_results["datasets"][dataset]
                    total_accuracy += dataset_result["accuracy"]
                    total_latency += dataset_result["latency_ms"]
                    total_cost += dataset_result["latency_ms"] * 0.00001
                    count += 1

                if count > 0:
                    model_results["mean_accuracy"] = total_accuracy / count
                    model_results["mean_latency_ms"] = total_latency / count
                    model_results["total_cost_usd"] = total_cost

                results.append(model_results)
            except Exception as e:
                logger.error(f"Model compare error for {model_name}: {e}")
                results.append(
                    {
                        "model": model_name,
                        "provider": provider,
                        "error": "模型执行失败",
                    }
                )

        return success_response(
            {
                "models": results,
                "is_simulated": True,
                "warning": "此端点返回模拟数据，仅供演示。生产环境请接入真实 benchmark 评估。",
                "datasets": datasets,
                "summary": {
                    "best_accuracy": (
                        max(results, key=lambda x: x.get("mean_accuracy", 0)).get("model")
                        if results
                        else None
                    ),
                    "fastest": (
                        min(results, key=lambda x: x.get("mean_latency_ms", float("inf"))).get(
                            "model"
                        )
                        if results
                        else None
                    ),
                },
            }
        )
    except Exception as e:
        logger.error(f"Failed to compare models: {e}")
        return error_response(500, "模型对比失败")


@router.get("/cost")
async def get_cost_metrics():
    """获取成本指标"""
    try:
        from src.infra.cost_governance import cost_governance

        metrics = cost_governance.get_metrics()
        budget_check = cost_governance.check_budget()

        return success_response(
            {
                "daily_cost_usd": metrics.daily_cost_usd,
                "weekly_cost_usd": metrics.weekly_cost_usd,
                "monthly_cost_usd": metrics.monthly_cost_usd,
                "avg_latency_ms": metrics.avg_latency_ms,
                "p50_latency_ms": metrics.p50_latency_ms,
                "p95_latency_ms": metrics.p95_latency_ms,
                "p99_latency_ms": metrics.p99_latency_ms,
                "total_requests": metrics.total_requests,
                "avg_tokens_per_request": metrics.avg_tokens_per_request,
                "budget_status": {
                    "daily_budget_ok": budget_check["daily_budget_ok"],
                    "daily_usage_percent": budget_check["daily_usage_percent"],
                    "daily_limit": cost_governance.daily_cost_limit,
                },
                "top_models_by_cost": cost_governance.get_top_models_by_cost(),
            }
        )
    except Exception as e:
        logger.error(f"Failed to get cost metrics: {e}")
        return error_response(500, "获取成本指标失败")


# ==================== 模型版本管理 ====================


@router.post("/models/versions")
async def register_model_version(
    data: dict,
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_MODEL_VERSIONS)),
):
    """注册模型版本

    需要 MANAGE_MODEL_VERSIONS 权限。
    """
    try:
        from src.domain.model_versioning import ModelVersionRegistry

        model_name = data.get("model_name")
        version = data.get("version")
        provider = data.get("provider")
        description = data.get("description", "")
        is_active = data.get("is_active", False)

        if not model_name or not version or not provider:
            return error_response(400, "model_name, version, provider 必填")

        model_version = ModelVersionRegistry.register(
            model_name=model_name,
            version=version,
            provider=provider,
            description=description,
            is_active=is_active,
        )

        return success_response(
            {
                "model_name": model_version.model_name,
                "version": model_version.version,
                "provider": model_version.provider,
                "description": model_version.description,
                "is_active": model_version.is_active,
                "created_at": model_version.created_at,
            }
        )
    except Exception as e:
        logger.error(f"Failed to register model version: {e}")
        return error_response(500, "注册模型版本失败")


@router.get("/models/{model_name}/versions")
async def get_model_versions(
    model_name: str,
    current_user: dict = Depends(PermissionDependency(Permission.VIEW_BENCHMARK)),
):
    """获取模型版本列表

    需要 VIEW_BENCHMARK 权限。
    """
    try:
        from src.domain.model_versioning import ModelVersionRegistry

        versions = ModelVersionRegistry.get_versions(model_name)

        if not versions:
            return success_response({"model_name": model_name, "versions": []})

        return success_response(
            {
                "model_name": model_name,
                "versions": [
                    {
                        "version": v.version,
                        "provider": v.provider,
                        "description": v.description,
                        "is_active": v.is_active,
                        "created_at": v.created_at,
                    }
                    for v in versions
                ],
            }
        )
    except Exception as e:
        logger.error(f"Failed to get model versions: {e}")
        return error_response(500, "获取模型版本失败")


@router.get("/models/{model_name}/versions/latest")
async def get_latest_version(
    model_name: str,
    current_user: dict = Depends(PermissionDependency(Permission.VIEW_BENCHMARK)),
):
    """获取模型最新版本

    需要 VIEW_BENCHMARK 权限。
    """
    try:
        from src.domain.model_versioning import ModelVersionRegistry

        latest = ModelVersionRegistry.get_latest(model_name)

        if not latest:
            return error_response(404, f"模型 '{model_name}' 暂无版本")

        return success_response(
            {
                "model_name": latest.model_name,
                "version": latest.version,
                "provider": latest.provider,
                "description": latest.description,
                "is_active": latest.is_active,
                "created_at": latest.created_at,
            }
        )
    except Exception as e:
        logger.error(f"Failed to get latest version: {e}")
        return error_response(500, "获取最新版本失败")


@router.get("/models/{model_name}/versions/compare")
async def compare_model_versions(
    model_name: str,
    v1: str,
    v2: str,
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_MODEL_VERSIONS)),
):
    """对比两个模型版本

    需要 MANAGE_MODEL_VERSIONS 权限。
    """
    try:
        from src.domain.model_versioning import ModelVersionRegistry

        comparison = ModelVersionRegistry.compare_versions(model_name, v1, v2)

        if not comparison:
            return error_response(404, "版本对比失败，版本不存在")

        return success_response(
            {
                "model_name": model_name,
                "version_1": comparison.get("version_1"),
                "version_2": comparison.get("version_2"),
                "comparison": comparison.get("comparison"),
            }
        )
    except Exception as e:
        logger.error(f"Failed to compare model versions: {e}")
        return error_response(500, "版本对比失败")


@router.post("/models/{model_name}/versions/{version}/activate")
async def activate_version(
    model_name: str,
    version: str,
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_MODEL_VERSIONS)),
):
    """激活模型版本

    需要 MANAGE_MODEL_VERSIONS 权限。
    """
    try:
        from src.domain.model_versioning import ModelVersionRegistry

        success = ModelVersionRegistry.activate_version(model_name, version)

        if not success:
            return error_response(404, f"版本 '{version}' 不存在")

        return success_response({"message": f"版本 '{version}' 已激活"})
    except Exception as e:
        logger.error(f"Failed to activate version: {e}")
        return error_response(500, "激活版本失败")


@router.delete("/models/{model_name}/versions/{version}")
async def delete_version(
    model_name: str,
    version: str,
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_MODEL_VERSIONS)),
):
    """删除模型版本

    需要 MANAGE_MODEL_VERSIONS 权限。
    """
    try:
        from src.domain.model_versioning import ModelVersionRegistry

        success = ModelVersionRegistry.delete_version(model_name, version)

        if not success:
            return error_response(404, f"版本 '{version}' 不存在")

        return success_response({"message": f"版本 '{version}' 已删除"})
    except Exception as e:
        logger.error(f"Failed to delete version: {e}")
        return error_response(500, "删除版本失败")
