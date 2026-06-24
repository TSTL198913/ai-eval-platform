"""
变异测试 API

提供变异测试运行、报告获取等接口。
"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.common import error_response, success_response
from src.api.dependencies import PermissionDependency
from src.infra.security import Permission

router = APIRouter(prefix="/api/v1/mutation-tests", tags=["变异测试"])


class MutationTestRequest(BaseModel):
    model_name: str = Field(..., description="模型名称")
    dataset_id: str = Field(..., description="数据集ID")
    operators: list[str] | None = Field(None, description="变异算子列表")
    sample_count: int = Field(default=10, description="采样数量")


class MutationTestResponse(BaseModel):
    test_id: str
    model_name: str
    dataset_id: str
    operators: list[str]
    kill_rate: float
    total_mutants: int
    killed_mutants: int
    survived_mutants: int
    report: dict[str, Any]
    timestamp: str


@router.post("/run")
async def run_mutation_test(
    request: MutationTestRequest,
    current_user: dict = Depends(PermissionDependency(Permission.RUN_MUTATION_TEST)),
) -> dict[str, Any]:
    """
    运行变异测试

    需要 RUN_MUTATION_TEST 权限。

    对模型进行变异测试，评估其鲁棒性。
    """
    try:
        import uuid
        from datetime import datetime, timezone

        from src.domain.testing.mutation_testing import MutationTester

        tester = MutationTester()
        test_id = f"mt_{uuid.uuid4().hex[:8]}"

        result = tester.run_mutation_tests(
            model_name=request.model_name,
            dataset_id=request.dataset_id,
            operators=request.operators,
            sample_count=request.sample_count,
        )

        return success_response(
            {
                "test_id": test_id,
                "model_name": request.model_name,
                "dataset_id": request.dataset_id,
                "operators": result.get("operators", []),
                "kill_rate": result.get("kill_rate", 0.0),
                "total_mutants": result.get("total_mutants", 0),
                "killed_mutants": result.get("killed_mutants", 0),
                "survived_mutants": result.get("survived_mutants", 0),
                "report": result.get("report", {}),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception as e:
        return error_response(500, f"变异测试失败: {str(e)}")


@router.get("/report/{test_id}")
async def get_report(
    test_id: str,
    current_user: dict = Depends(PermissionDependency(Permission.VIEW_MUTATION_REPORT)),
) -> dict[str, Any]:
    """
    获取变异测试报告

    需要 VIEW_MUTATION_REPORT 权限。
    """
    try:
        from src.domain.testing.mutation_testing import MutationTester

        tester = MutationTester()
        report = tester.get_report(test_id)

        if not report:
            return error_response(404, f"报告 '{test_id}' 不存在")

        return success_response(report)
    except Exception as e:
        return error_response(500, f"获取报告失败: {str(e)}")


@router.get("/operators")
async def list_operators(
    current_user: dict = Depends(PermissionDependency(Permission.VIEW_MUTATION_REPORT)),
) -> dict[str, Any]:
    """
    获取变异算子列表

    需要 VIEW_MUTATION_REPORT 权限。
    """
    try:
        from src.domain.testing.mutation_testing import MutationTester

        tester = MutationTester()
        operators = tester.get_operators()

        return success_response(operators)
    except Exception as e:
        return error_response(500, f"获取算子列表失败: {str(e)}")


@router.get("/kill-rate/{model_name}")
async def get_kill_rate(
    model_name: str,
    current_user: dict = Depends(PermissionDependency(Permission.VIEW_MUTATION_REPORT)),
) -> dict[str, Any]:
    """
    获取模型的杀错率

    需要 VIEW_MUTATION_REPORT 权限。
    """
    try:
        from src.domain.testing.mutation_testing import MutationTester

        tester = MutationTester()
        kill_rate = tester.get_kill_rate(model_name)

        return success_response(
            {
                "model_name": model_name,
                "kill_rate": kill_rate,
            }
        )
    except Exception as e:
        return error_response(500, f"获取杀错率失败: {str(e)}")


@router.get("/history/{model_name}")
async def get_test_history(
    model_name: str,
    limit: int = 10,
    current_user: dict = Depends(PermissionDependency(Permission.VIEW_MUTATION_REPORT)),
) -> dict[str, Any]:
    """
    获取模型的变异测试历史

    需要 VIEW_MUTATION_REPORT 权限。
    """
    try:
        from src.domain.testing.mutation_testing import MutationTester

        tester = MutationTester()
        history = tester.get_history(model_name, limit=limit)

        return success_response(
            {
                "model_name": model_name,
                "history": history,
                "total_tests": len(history),
            }
        )
    except Exception as e:
        return error_response(500, f"获取测试历史失败: {str(e)}")
