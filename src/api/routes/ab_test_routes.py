"""
A/B Testing API

提供 A/B 测试的创建、管理、结果分析接口。
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.api.dependencies import (
    PermissionDependency,
)
from src.domain.ab_testing import ABTestAPI, ABTestManager, ABTestStatus
from src.infra.security import Permission

router = APIRouter(prefix="/api/v1/ab-tests", tags=["A/B Testing"])


# Pydantic 模型
class ABTestCreate(BaseModel):
    test_id: str = Field(..., description="测试ID")
    model_a: str = Field(..., description="模型A名称")
    model_b: str = Field(..., description="模型B名称")
    description: str | None = Field(None, description="测试描述")


class ABTestResultAdd(BaseModel):
    group: str = Field(..., description="组名: 'a' 或 'b'")
    result: dict[str, Any] = Field(..., description="测试结果数据")


class ABTestResponse(BaseModel):
    test_id: str
    status: str
    group_a: str
    group_b: str
    description: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None


class ABTestDetailResponse(BaseModel):
    test_id: str
    status: str
    group_a: dict[str, Any]
    group_b: dict[str, Any]
    statistics: dict[str, Any] | None = None
    description: str | None = None


class ABTestListResponse(BaseModel):
    tests: list[ABTestResponse]
    total: int


@router.post("", response_model=ABTestResponse, status_code=status.HTTP_201_CREATED)
async def create_ab_test(
    test_data: ABTestCreate,
    current_user: dict = Depends(PermissionDependency(Permission.CREATE_AB_TEST)),
) -> ABTestResponse:
    """
    创建 A/B 测试

    需要 CREATE_AB_TEST 权限。
    """
    # 检查测试ID是否已存在
    existing_test = ABTestManager.get_test(test_data.test_id)
    if existing_test:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"测试ID '{test_data.test_id}' 已存在",
        )

    # 创建测试
    result = ABTestAPI.create(test_data.test_id, test_data.model_a, test_data.model_b)

    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"],
        )

    # 获取创建的测试对象以添加额外信息
    test = ABTestManager.get_test(test_data.test_id)
    if test:
        test.description = test_data.description
        test.created_at = datetime.now(timezone.utc)

    return ABTestResponse(
        test_id=result["test_id"],
        status=result["status"],
        group_a=result["group_a"],
        group_b=result["group_b"],
        description=test_data.description,
        created_at=datetime.now(timezone.utc),
    )


@router.get("", response_model=ABTestListResponse)
async def list_ab_tests(
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_AB_TEST)),
) -> ABTestListResponse:
    """
    列出所有 A/B 测试

    需要 MANAGE_AB_TEST 权限。
    """
    tests = ABTestAPI.list()

    test_responses = [
        ABTestResponse(
            test_id=t["test_id"],
            status=t["status"],
            group_a=t["group_a"],
            group_b=t["group_b"],
        )
        for t in tests
    ]

    return ABTestListResponse(
        tests=test_responses,
        total=len(test_responses),
    )


@router.get("/{test_id}", response_model=ABTestDetailResponse)
async def get_ab_test(
    test_id: str,
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_AB_TEST)),
) -> ABTestDetailResponse:
    """
    获取 A/B 测试详情

    需要 MANAGE_AB_TEST 权限。
    """
    result = ABTestAPI.get_result(test_id)

    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result["error"],
        )

    return ABTestDetailResponse(
        test_id=result["test_id"],
        status=result["status"],
        group_a=result["group_a"],
        group_b=result["group_b"],
        statistics=result.get("statistics"),
    )


@router.post("/{test_id}/results", response_model=dict[str, Any])
async def add_ab_test_result(
    test_id: str,
    result_data: ABTestResultAdd,
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_AB_TEST)),
) -> dict[str, Any]:
    """
    添加测试结果

    需要 MANAGE_AB_TEST 权限。
    """
    # 验证组名
    if result_data.group.lower() not in ["a", "b"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="组名必须是 'a' 或 'b'",
        )

    result = ABTestAPI.add_result(test_id, result_data.group.lower(), result_data.result)

    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result["error"],
        )

    return result


@router.post("/{test_id}/complete", response_model=ABTestDetailResponse)
async def complete_ab_test(
    test_id: str,
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_AB_TEST)),
) -> ABTestDetailResponse:
    """
    完成 A/B 测试

    需要 MANAGE_AB_TEST 权限。

    完成后会计算统计结果。
    """
    result = ABTestAPI.complete(test_id)

    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result["error"],
        )

    # 获取完整结果
    full_result = ABTestAPI.get_result(test_id)

    return ABTestDetailResponse(
        test_id=full_result["test_id"],
        status=full_result["status"],
        group_a=full_result["group_a"],
        group_b=full_result["group_b"],
        statistics=full_result.get("statistics"),
    )


@router.delete("/{test_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ab_test(
    test_id: str,
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_AB_TEST)),
) -> None:
    """
    删除 A/B 测试

    需要 MANAGE_AB_TEST 权限。
    """
    test = ABTestManager.get_test(test_id)
    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"测试 '{test_id}' 不存在",
        )

    ABTestManager.delete_test(test_id)


@router.get("/{test_id}/statistics", response_model=dict[str, Any])
async def get_ab_test_statistics(
    test_id: str,
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_AB_TEST)),
) -> dict[str, Any]:
    """
    获取 A/B 测试统计结果

    需要 MANAGE_AB_TEST 权限。

    返回详细的统计分析数据，包括：
    - 平均分数
    - 标准差
    - 置信区间
    - 显著性检验结果
    """
    test = ABTestManager.get_test(test_id)
    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"测试 '{test_id}' 不存在",
        )

    # 如果测试未完成，先计算统计
    if test.status != ABTestStatus.COMPLETED:
        test.calculate_statistics()

    return test.statistics


@router.get("/active", response_model=list[ABTestResponse])
async def get_active_tests(
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_AB_TEST)),
) -> list[ABTestResponse]:
    """
    获取进行中的 A/B 测试

    需要 MANAGE_AB_TEST 权限。
    """
    all_tests = ABTestManager.list_tests()
    active_tests = [t for t in all_tests if t.status == ABTestStatus.RUNNING]

    return [
        ABTestResponse(
            test_id=t.test_id,
            status=t.status.value,
            group_a=t.group_a["name"],
            group_b=t.group_b["name"],
        )
        for t in active_tests
    ]


@router.get("/completed", response_model=list[ABTestResponse])
async def get_completed_tests(
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_AB_TEST)),
) -> list[ABTestResponse]:
    """
    获取已完成的 A/B 测试

    需要 MANAGE_AB_TEST 权限。
    """
    all_tests = ABTestManager.list_tests()
    completed_tests = [t for t in all_tests if t.status == ABTestStatus.COMPLETED]

    return [
        ABTestResponse(
            test_id=t.test_id,
            status=t.status.value,
            group_a=t.group_a["name"],
            group_b=t.group_b["name"],
        )
        for t in completed_tests
    ]
