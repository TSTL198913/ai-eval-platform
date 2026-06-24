"""
成本治理 API

提供成本报告、预算管理、用量统计等接口。
"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.common import error_response, success_response
from src.api.dependencies import PermissionDependency
from src.infra.security import Permission

router = APIRouter(prefix="/api/v1/costs", tags=["成本治理"])


class BudgetRequest(BaseModel):
    model_name: str | None = Field(None, description="模型名称（为空则设置全局预算）")
    daily_budget: float = Field(..., description="每日预算（美元）")
    monthly_budget: float | None = Field(None, description="每月预算（美元）")


class BudgetResponse(BaseModel):
    model_name: str | None
    daily_budget: float
    monthly_budget: float | None
    daily_usage: float
    daily_usage_percent: float
    status: str


@router.get("/usage")
async def get_usage(
    start_date: str | None = None,
    end_date: str | None = None,
    model_name: str | None = None,
    current_user: dict = Depends(PermissionDependency(Permission.VIEW_COST_REPORT)),
) -> dict[str, Any]:
    """
    获取用量统计

    需要 VIEW_COST_REPORT 权限。
    """
    try:
        from src.infra.cost_governance import cost_governance

        usage = cost_governance.get_usage(
            start_date=start_date,
            end_date=end_date,
            model_name=model_name,
        )

        return success_response(usage)
    except Exception as e:
        return error_response(500, f"获取用量失败: {str(e)}")


@router.get("/report")
async def get_cost_report(
    period: str = "daily",
    current_user: dict = Depends(PermissionDependency(Permission.VIEW_COST_REPORT)),
) -> dict[str, Any]:
    """
    获取成本报告

    需要 VIEW_COST_REPORT 权限。

    Args:
        period: 报告周期: daily, weekly, monthly
    """
    try:
        from src.infra.cost_governance import cost_governance

        report = cost_governance.get_cost_report(period=period)

        return success_response(report)
    except Exception as e:
        return error_response(500, f"获取报告失败: {str(e)}")


@router.get("/by-model/{model_name}")
async def get_cost_by_model(
    model_name: str,
    period: str = "daily",
    current_user: dict = Depends(PermissionDependency(Permission.VIEW_COST_REPORT)),
) -> dict[str, Any]:
    """
    获取指定模型的成本统计

    需要 VIEW_COST_REPORT 权限。
    """
    try:
        from src.infra.cost_governance import cost_governance

        report = cost_governance.get_cost_by_model(model_name, period=period)

        return success_response(report)
    except Exception as e:
        return error_response(500, f"获取模型成本失败: {str(e)}")


@router.post("/budget")
async def set_budget(
    request: BudgetRequest,
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_BUDGET)),
) -> dict[str, Any]:
    """
    设置预算

    需要 MANAGE_BUDGET 权限。
    """
    try:
        from src.infra.cost_governance import cost_governance

        result = cost_governance.set_budget(
            model_name=request.model_name,
            daily_budget=request.daily_budget,
            monthly_budget=request.monthly_budget,
        )

        return success_response(
            {
                "model_name": request.model_name,
                "daily_budget": request.daily_budget,
                "monthly_budget": request.monthly_budget,
                "daily_usage": result.get("daily_usage", 0),
                "daily_usage_percent": result.get("daily_usage_percent", 0),
                "status": "success",
            }
        )
    except Exception as e:
        return error_response(500, f"设置预算失败: {str(e)}")


@router.get("/budget/{model_name}")
async def get_budget(
    model_name: str,
    current_user: dict = Depends(PermissionDependency(Permission.VIEW_COST_REPORT)),
) -> dict[str, Any]:
    """
    获取模型预算状态

    需要 VIEW_COST_REPORT 权限。
    """
    try:
        from src.infra.cost_governance import cost_governance

        status = cost_governance.get_budget_status(model_name)

        return success_response(
            {
                "model_name": model_name,
                "daily_budget": status.get("daily_limit", 0),
                "monthly_budget": status.get("monthly_limit"),
                "daily_usage": status.get("daily_usage", 0),
                "daily_usage_percent": status.get("daily_usage_percent", 0),
                "status": "ok" if status.get("daily_budget_ok", True) else "warning",
            }
        )
    except Exception as e:
        return error_response(500, f"获取预算失败: {str(e)}")


@router.put("/budget/{model_name}")
async def update_budget(
    model_name: str,
    request: BudgetRequest,
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_BUDGET)),
) -> dict[str, Any]:
    """
    更新模型预算

    需要 MANAGE_BUDGET 权限。
    """
    try:
        from src.infra.cost_governance import cost_governance

        success = cost_governance.update_budget(
            model_name=model_name,
            daily_budget=request.daily_budget,
            monthly_budget=request.monthly_budget,
        )

        if not success:
            return error_response(404, f"模型 '{model_name}' 预算不存在")

        return success_response({"message": f"模型 '{model_name}' 预算已更新"})
    except Exception as e:
        return error_response(500, f"更新预算失败: {str(e)}")


@router.get("/top-models")
async def get_top_models_by_cost(
    limit: int = 10,
    current_user: dict = Depends(PermissionDependency(Permission.VIEW_COST_REPORT)),
) -> dict[str, Any]:
    """
    获取成本最高的模型列表

    需要 VIEW_COST_REPORT 权限。
    """
    try:
        from src.infra.cost_governance import cost_governance

        top_models = cost_governance.get_top_models_by_cost(limit=limit)

        return success_response({"top_models": top_models})
    except Exception as e:
        return error_response(500, f"获取成本排名失败: {str(e)}")


@router.get("/alerts")
async def get_cost_alerts(
    current_user: dict = Depends(PermissionDependency(Permission.VIEW_COST_REPORT)),
) -> dict[str, Any]:
    """
    获取成本告警

    需要 VIEW_COST_REPORT 权限。
    """
    try:
        from src.infra.cost_governance import cost_governance

        alerts = cost_governance.get_alerts()

        return success_response({"alerts": alerts})
    except Exception as e:
        return error_response(500, f"获取告警失败: {str(e)}")
