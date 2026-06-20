"""模型管理路由模块

提供模型列表查询、模型对比评测、成本指标查询等API端点。
"""

import logging

from fastapi import APIRouter

from src.api.common import error_response, success_response

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
