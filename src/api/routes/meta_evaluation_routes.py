"""
元评估 API

提供评估结果冲突检测、解决等接口。
"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.common import error_response, success_response
from src.api.dependencies import PermissionDependency
from src.infra.security import Permission

router = APIRouter(prefix="/api/v1/meta", tags=["元评估"])


class ConflictResolveRequest(BaseModel):
    resolution: str = Field(
        ..., description="解决方案: accept_new, revert_to_baseline, manual_review"
    )
    reason: str | None = Field(None, description="解决原因")


class ConflictResponse(BaseModel):
    case_id: str
    conflict_type: str
    new_result: dict[str, Any]
    baseline: dict[str, Any]
    severity: str
    status: str
    created_at: str | None = None


class ConflictStatsResponse(BaseModel):
    total_conflicts: int
    pending_conflicts: int
    resolved_conflicts: int
    by_severity: dict[str, int]
    by_type: dict[str, int]


@router.get("/conflicts")
async def get_conflicts(
    status_filter: str | None = None,
    current_user: dict = Depends(PermissionDependency(Permission.VIEW_META_CONFLICTS)),
) -> dict[str, Any]:
    """
    获取冲突列表

    需要 VIEW_META_CONFLICTS 权限。

    Args:
        status_filter: 状态过滤: pending, resolved, all
    """
    try:
        from src.domain.meta_evaluator import MetaEvaluator

        evaluator = MetaEvaluator()
        conflicts = evaluator.get_pending_conflicts()

        if status_filter == "resolved":
            conflicts = evaluator.get_resolved_conflicts()
        elif status_filter == "all":
            conflicts = evaluator.get_all_conflicts()

        return success_response(
            [
                {
                    "case_id": c.get("case_id"),
                    "conflict_type": c.get("conflict_type"),
                    "new_result": c.get("new_result"),
                    "baseline": c.get("baseline"),
                    "severity": c.get("severity", "medium"),
                    "status": c.get("status", "pending"),
                    "created_at": c.get("created_at"),
                }
                for c in conflicts
            ]
        )
    except Exception as e:
        return error_response(500, f"获取冲突失败: {str(e)}")


@router.get("/conflicts/{case_id}")
async def get_conflict(
    case_id: str,
    current_user: dict = Depends(PermissionDependency(Permission.VIEW_META_CONFLICTS)),
) -> dict[str, Any]:
    """
    获取冲突详情

    需要 VIEW_META_CONFLICTS 权限。
    """
    try:
        from src.domain.meta_evaluator import MetaEvaluator

        evaluator = MetaEvaluator()
        conflict = evaluator.get_conflict(case_id)

        if not conflict:
            return error_response(404, f"冲突 '{case_id}' 不存在")

        return success_response(
            {
                "case_id": conflict.get("case_id"),
                "conflict_type": conflict.get("conflict_type"),
                "new_result": conflict.get("new_result"),
                "baseline": conflict.get("baseline"),
                "severity": conflict.get("severity", "medium"),
                "status": conflict.get("status", "pending"),
                "created_at": conflict.get("created_at"),
            }
        )
    except Exception as e:
        return error_response(500, f"获取冲突详情失败: {str(e)}")


@router.post("/conflicts/{case_id}/resolve")
async def resolve_conflict(
    case_id: str,
    request: ConflictResolveRequest,
    current_user: dict = Depends(PermissionDependency(Permission.RESOLVE_META_CONFLICT)),
) -> dict[str, Any]:
    """
    解决冲突

    需要 RESOLVE_META_CONFLICT 权限。

    Args:
        resolution: 解决方案:
            - accept_new: 接受新结果
            - revert_to_baseline: 回退到基线
            - manual_review: 人工审核
    """
    try:
        from src.domain.meta_evaluator import MetaEvaluator

        evaluator = MetaEvaluator()
        evaluator.resolve_conflict(
            case_id=case_id,
            resolution=request.resolution,
            reason=request.reason,
        )

        return success_response(
            {
                "case_id": case_id,
                "status": "resolved",
                "resolution": request.resolution,
                "reason": request.reason,
            }
        )
    except Exception as e:
        return error_response(500, f"解决冲突失败: {str(e)}")


@router.get("/stats")
async def get_stats(
    current_user: dict = Depends(PermissionDependency(Permission.VIEW_META_CONFLICTS)),
) -> dict[str, Any]:
    """
    获取冲突统计

    需要 VIEW_META_CONFLICTS 权限。
    """
    try:
        from src.domain.meta_evaluator import MetaEvaluator

        evaluator = MetaEvaluator()
        stats = evaluator.get_conflict_stats()

        return success_response(
            {
                "total_conflicts": stats.get("total_conflicts", 0),
                "pending_conflicts": stats.get("pending_conflicts", 0),
                "resolved_conflicts": stats.get("resolved_conflicts", 0),
                "by_severity": stats.get("by_severity", {}),
                "by_type": stats.get("by_type", {}),
            }
        )
    except Exception as e:
        return error_response(500, f"获取统计失败: {str(e)}")


@router.post("/calibrate")
async def trigger_calibration(
    current_user: dict = Depends(PermissionDependency(Permission.RESOLVE_META_CONFLICT)),
) -> dict[str, Any]:
    """
    触发校准

    需要 RESOLVE_META_CONFLICT 权限。

    对评估器进行自动校准，基于黄金数据集更新基线。
    """
    try:
        from src.domain.meta_evaluator import MetaEvaluator

        evaluator = MetaEvaluator()
        result = evaluator.calibrate()

        return success_response(
            {
                "status": "calibrated",
                "updated_baselines": result.get("updated_baselines", 0),
                "message": result.get("message", "校准完成"),
            }
        )
    except Exception as e:
        return error_response(500, f"校准失败: {str(e)}")


@router.post("/analyze")
async def analyze_results(
    request: dict,
    current_user: dict = Depends(PermissionDependency(Permission.VIEW_META_CONFLICTS)),
) -> dict[str, Any]:
    """
    分析评估结果

    需要 VIEW_META_CONFLICTS 权限。

    对一组评估结果进行元分析，检测异常模式。
    """
    try:
        from src.domain.meta_evaluator import MetaEvaluator

        evaluator = MetaEvaluator()
        results = request.get("results", [])

        if not results:
            return error_response(400, "results 必填")

        analysis = evaluator.analyze_results(results)

        return success_response(analysis)
    except Exception as e:
        return error_response(500, f"分析失败: {str(e)}")
