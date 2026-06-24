"""
评估器版本管理 API

提供评估器版本列表、详情、回滚、激活等接口。
"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.api.common import error_response, success_response
from src.api.dependencies import PermissionDependency
from src.infra.security import Permission

router = APIRouter(prefix="/api/v1/evaluators/versions", tags=["评估器版本管理"])


class EvaluatorVersionResponse(BaseModel):
    evaluator_id: str
    version: str
    name: str
    description: str | None = None
    is_active: bool
    created_at: str | None = None


@router.get("")
async def list_versions(
    evaluator_id: str | None = None,
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_EVALUATOR_VERSIONS)),
) -> dict[str, Any]:
    """
    获取评估器版本列表

    需要 MANAGE_EVALUATOR_VERSIONS 权限。

    Args:
        evaluator_id: 评估器ID（可选，过滤特定评估器）
    """
    try:
        from src.domain.evaluator_version import (
            EvaluatorVersionManagerAPI as EvaluatorVersionManager,
        )

        manager = EvaluatorVersionManager()
        versions = manager.list_versions(evaluator_id=evaluator_id)

        return success_response(
            [
                {
                    "evaluator_id": v.get("evaluator_id"),
                    "version": v.get("version"),
                    "name": v.get("name"),
                    "description": v.get("description"),
                    "is_active": v.get("is_active", False),
                    "created_at": v.get("created_at"),
                }
                for v in versions
            ]
        )
    except Exception as e:
        return error_response(500, f"获取版本列表失败: {str(e)}")


@router.get("/history/{evaluator_id}")
async def get_version_history(
    evaluator_id: str,
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_EVALUATOR_VERSIONS)),
) -> dict[str, Any]:
    """
    获取评估器版本历史

    需要 MANAGE_EVALUATOR_VERSIONS 权限。
    """
    try:
        from src.domain.evaluator_version import (
            EvaluatorVersionManagerAPI as EvaluatorVersionManager,
        )

        manager = EvaluatorVersionManager()
        history = manager.get_history(evaluator_id)

        return success_response(
            {
                "evaluator_id": evaluator_id,
                "history": history,
                "total_versions": len(history),
            }
        )
    except Exception as e:
        return error_response(500, f"获取版本历史失败: {str(e)}")


@router.get("/{evaluator_id}")
async def get_evaluator_versions(
    evaluator_id: str,
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_EVALUATOR_VERSIONS)),
) -> dict[str, Any]:
    """
    获取评估器的所有版本

    需要 MANAGE_EVALUATOR_VERSIONS 权限。
    """
    try:
        from src.domain.evaluator_version import (
            EvaluatorVersionManagerAPI as EvaluatorVersionManager,
        )

        manager = EvaluatorVersionManager()
        versions = manager.get_versions(evaluator_id)

        return success_response(
            [
                {
                    "evaluator_id": v.get("evaluator_id"),
                    "version": v.get("version"),
                    "name": v.get("name"),
                    "description": v.get("description"),
                    "is_active": v.get("is_active", False),
                    "created_at": v.get("created_at"),
                }
                for v in versions
            ]
        )
    except Exception as e:
        return error_response(500, f"获取评估器版本失败: {str(e)}")


@router.get("/{evaluator_id}/{version}")
async def get_version_detail(
    evaluator_id: str,
    version: str,
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_EVALUATOR_VERSIONS)),
) -> dict[str, Any]:
    """
    获取评估器版本详情

    需要 MANAGE_EVALUATOR_VERSIONS 权限。
    """
    try:
        from src.domain.evaluator_version import (
            EvaluatorVersionManagerAPI as EvaluatorVersionManager,
        )

        manager = EvaluatorVersionManager()
        version_info = manager.get_version(evaluator_id, version)

        if not version_info:
            return error_response(404, f"版本 '{version}' 不存在")

        return success_response(
            {
                "evaluator_id": version_info.get("evaluator_id"),
                "version": version_info.get("version"),
                "name": version_info.get("name"),
                "description": version_info.get("description"),
                "is_active": version_info.get("is_active", False),
                "created_at": version_info.get("created_at"),
            }
        )
    except Exception as e:
        return error_response(500, f"获取版本详情失败: {str(e)}")


@router.post("/{evaluator_id}/rollback")
async def rollback_version(
    evaluator_id: str,
    request: dict,
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_EVALUATOR_VERSIONS)),
) -> dict[str, Any]:
    """
    回滚评估器版本

    需要 MANAGE_EVALUATOR_VERSIONS 权限。
    """
    try:
        from src.domain.evaluator_version import (
            EvaluatorVersionManagerAPI as EvaluatorVersionManager,
        )

        manager = EvaluatorVersionManager()
        target_version = request.get("version")

        if not target_version:
            return error_response(400, "version 必填")

        success = manager.rollback(evaluator_id, target_version)

        if not success:
            return error_response(404, f"版本 '{target_version}' 不存在")

        return success_response(
            {
                "evaluator_id": evaluator_id,
                "version": target_version,
                "status": "rolled_back",
            }
        )
    except Exception as e:
        return error_response(500, f"回滚版本失败: {str(e)}")


@router.post("/{evaluator_id}/{version}/activate")
async def activate_version(
    evaluator_id: str,
    version: str,
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_EVALUATOR_VERSIONS)),
) -> dict[str, Any]:
    """
    激活评估器版本

    需要 MANAGE_EVALUATOR_VERSIONS 权限。
    """
    try:
        from src.domain.evaluator_version import (
            EvaluatorVersionManagerAPI as EvaluatorVersionManager,
        )

        manager = EvaluatorVersionManager()
        success = manager.activate(evaluator_id, version)

        if not success:
            return error_response(404, f"版本 '{version}' 不存在")

        return success_response(
            {
                "evaluator_id": evaluator_id,
                "version": version,
                "status": "activated",
            }
        )
    except Exception as e:
        return error_response(500, f"激活版本失败: {str(e)}")


@router.delete("/{evaluator_id}/{version}")
async def delete_version(
    evaluator_id: str,
    version: str,
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_EVALUATOR_VERSIONS)),
) -> dict[str, Any]:
    """
    删除评估器版本

    需要 MANAGE_EVALUATOR_VERSIONS 权限。

    注意：不能删除当前激活的版本。
    """
    try:
        from src.domain.evaluator_version import (
            EvaluatorVersionManagerAPI as EvaluatorVersionManager,
        )

        manager = EvaluatorVersionManager()
        success = manager.delete(evaluator_id, version)

        if not success:
            return error_response(404, f"版本 '{version}' 不存在或无法删除")

        return success_response({"message": f"版本 '{version}' 已删除"})
    except Exception as e:
        return error_response(500, f"删除版本失败: {str(e)}")
