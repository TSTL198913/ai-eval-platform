"""
质量门禁 API

提供质量检查、红队测试、蓝队测试等接口。
"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.common import error_response, success_response
from src.api.dependencies import PermissionDependency
from src.infra.security import Permission

router = APIRouter(prefix="/api/v1/quality-gates", tags=["质量门禁"])


class QualityCheckRequest(BaseModel):
    model_name: str = Field(..., description="模型名称")
    level: str = Field(default="basic", description="检查级别: basic, standard, strict")
    dataset_id: str | None = Field(None, description="数据集ID")
    sample_count: int = Field(default=10, description="采样数量")


class QualityCheckResponse(BaseModel):
    check_id: str
    model_name: str
    level: str
    passed: bool
    score: float
    metrics: dict[str, Any]
    issues: list[dict[str, Any]]
    timestamp: str


class QualityGateConfigResponse(BaseModel):
    level: str
    thresholds: dict[str, float]
    check_items: list[str]
    description: str


@router.post("/check")
async def run_quality_check(
    request: QualityCheckRequest,
    current_user: dict = Depends(PermissionDependency(Permission.RUN_QUALITY_GATE)),
) -> dict[str, Any]:
    """
    执行质量门禁检查

    需要 RUN_QUALITY_GATE 权限。
    """
    try:
        import uuid
        from datetime import datetime, timezone

        from src.domain.testing.quality_gates import QualityAssuranceManager

        manager = QualityAssuranceManager()
        check_id = f"qc_{uuid.uuid4().hex[:8]}"

        result = manager.check(
            model_name=request.model_name,
            level=request.level,
            dataset_id=request.dataset_id,
            sample_count=request.sample_count,
        )

        return success_response(
            {
                "check_id": check_id,
                "model_name": request.model_name,
                "level": request.level,
                "passed": result.get("passed", False),
                "score": result.get("score", 0.0),
                "metrics": result.get("metrics", {}),
                "issues": result.get("issues", []),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception as e:
        return error_response(500, f"质量检查失败: {str(e)}")


@router.get("/{level}")
async def get_gate_config(
    level: str,
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_QUALITY_CONFIG)),
) -> dict[str, Any]:
    """
    获取质量门禁配置

    需要 MANAGE_QUALITY_CONFIG 权限。

    Args:
        level: 检查级别: basic, standard, strict
    """
    try:
        from src.domain.testing.quality_gates import QualityAssuranceManager

        manager = QualityAssuranceManager()
        config = manager.get_gate_config(level)

        if not config:
            return error_response(404, f"配置级别 '{level}' 不存在")

        return success_response(
            {
                "level": level,
                "thresholds": config.get("thresholds", {}),
                "check_items": config.get("check_items", []),
                "description": config.get("description", ""),
            }
        )
    except Exception as e:
        return error_response(500, f"获取配置失败: {str(e)}")


@router.get("/results/{check_id}")
async def get_check_result(
    check_id: str,
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_QUALITY_CONFIG)),
) -> dict[str, Any]:
    """
    获取检查结果

    需要 MANAGE_QUALITY_CONFIG 权限。
    """
    try:
        from src.domain.testing.quality_gates import QualityAssuranceManager

        manager = QualityAssuranceManager()
        result = manager.get_gate_result(check_id)

        if not result:
            return error_response(404, f"检查结果 '{check_id}' 不存在")

        return success_response(result)
    except Exception as e:
        return error_response(500, f"获取结果失败: {str(e)}")


@router.post("/red-team")
async def mark_red_team_test(
    request: dict,
    current_user: dict = Depends(PermissionDependency(Permission.RUN_QUALITY_GATE)),
) -> dict[str, Any]:
    """
    标记红队测试

    需要 RUN_QUALITY_GATE 权限。

    红队测试：模拟攻击者试图绕过安全限制。
    """
    try:
        from src.domain.testing.quality_gates import run_red_team_test

        result = run_red_team_test(
            model_name=request.get("model_name"),
            scenarios=request.get("scenarios", []),
        )

        return success_response(
            {
                "status": "red_team_test_completed",
                "model_name": request.get("model_name"),
                "scenarios": len(request.get("scenarios", [])),
                "passed": result.get("passed", False),
                "issues_found": result.get("issues_found", []),
            }
        )
    except Exception as e:
        return error_response(500, f"红队测试失败: {str(e)}")


@router.post("/blue-team")
async def mark_blue_team_test(
    request: dict,
    current_user: dict = Depends(PermissionDependency(Permission.RUN_QUALITY_GATE)),
) -> dict[str, Any]:
    """
    标记蓝队测试

    需要 RUN_QUALITY_GATE 权限。

    蓝队测试：防御者检测和响应攻击。
    """
    try:
        from src.domain.testing.quality_gates import run_blue_team_test

        result = run_blue_team_test(
            model_name=request.get("model_name"),
            test_cases=request.get("test_cases", []),
        )

        return success_response(
            {
                "status": "blue_team_test_completed",
                "model_name": request.get("model_name"),
                "test_cases": len(request.get("test_cases", [])),
                "detections": result.get("detections", []),
                "false_positives": result.get("false_positives", []),
            }
        )
    except Exception as e:
        return error_response(500, f"蓝队测试失败: {str(e)}")


@router.get("/history/{model_name}")
async def get_check_history(
    model_name: str,
    limit: int = 10,
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_QUALITY_CONFIG)),
) -> dict[str, Any]:
    """
    获取模型检查历史

    需要 MANAGE_QUALITY_CONFIG 权限。
    """
    try:
        from src.domain.testing.quality_gates import QualityAssuranceManager

        manager = QualityAssuranceManager()
        history = manager.get_check_history(model_name, limit=limit)

        return success_response(
            {
                "model_name": model_name,
                "history": history,
                "total": len(history),
            }
        )
    except Exception as e:
        return error_response(500, f"获取历史失败: {str(e)}")


@router.put("/{level}/config")
async def update_gate_config(
    level: str,
    config: dict,
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_QUALITY_CONFIG)),
) -> dict[str, Any]:
    """
    更新质量门禁配置

    需要 MANAGE_QUALITY_CONFIG 权限。
    """
    try:
        from src.domain.testing.quality_gates import QualityAssuranceManager

        manager = QualityAssuranceManager()
        success = manager.update_gate_config(level, config)

        if not success:
            return error_response(404, f"配置级别 '{level}' 不存在")

        return success_response({"message": f"配置 '{level}' 已更新"})
    except Exception as e:
        return error_response(500, f"更新配置失败: {str(e)}")
