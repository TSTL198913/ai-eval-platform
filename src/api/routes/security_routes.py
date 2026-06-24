"""
安全测试 API

提供 Prompt 注入测试、Jailbreak 测试、数据泄露检测等安全扫描接口。
"""

from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from src.api.common import error_response, success_response
from src.api.dependencies import PermissionDependency
from src.infra.security import Permission

router = APIRouter(prefix="/api/v1/security", tags=["安全测试"])


class SecurityTestRequest(BaseModel):
    prompt: str = Field(..., description="要测试的 Prompt")
    test_types: list[str] | None = Field(
        None, description="测试类型列表: injection, jailbreak, data_leakage, tool_poisoning"
    )


class SecurityRuleCreate(BaseModel):
    name: str = Field(..., description="规则名称")
    pattern: str = Field(..., description="正则表达式")
    category: str = Field(..., description="规则分类")
    severity: str = Field(default="medium", description="严重程度: low, medium, high, critical")
    description: str | None = Field(None, description="规则描述")


class SecurityRuleResponse(BaseModel):
    rule_id: str
    name: str
    pattern: str
    category: str
    severity: str
    description: str | None = None


class SecurityReportResponse(BaseModel):
    report_id: str
    prompt: str
    overall_status: str
    issues: list[dict[str, Any]]
    timestamp: str


@router.post("/test")
async def test_prompt(
    request: SecurityTestRequest,
    current_user: dict = Depends(PermissionDependency(Permission.RUN_SECURITY_TEST)),
) -> dict[str, Any]:
    """
    测试单一 Prompt 的安全性

    需要 RUN_SECURITY_TEST 权限。
    """
    try:
        from src.domain.security.security_tester import SecurityTester

        tester = SecurityTester()

        if request.test_types:
            results = {}
            for test_type in request.test_types:
                if test_type == "injection":
                    result = tester.test_prompt_injection(request.prompt)
                elif test_type == "jailbreak":
                    result = tester.test_jailbreak(request.prompt)
                elif test_type == "data_leakage":
                    result = tester.test_data_leakage(request.prompt)
                elif test_type == "tool_poisoning":
                    result = tester.test_tool_poisoning(request.prompt)
                else:
                    continue
                results[test_type] = result
            return success_response(results)

        full_report = tester.run_security_tests(request.prompt)

        return success_response(
            {
                "prompt": request.prompt,
                "overall_status": "safe" if full_report.is_safe else "unsafe",
                "issues": full_report.to_dict().get("issues", []),
                "score": full_report.score,
            }
        )
    except Exception as e:
        return error_response(500, f"安全测试失败: {str(e)}")


@router.post("/scan")
async def full_scan(
    request: dict,
    current_user: dict = Depends(PermissionDependency(Permission.RUN_SECURITY_TEST)),
) -> dict[str, Any]:
    """
    完整安全扫描

    需要 RUN_SECURITY_TEST 权限。

    对多个 Prompt 进行全面安全扫描。
    """
    try:
        import uuid
        from datetime import datetime, timezone

        from src.domain.security.security_tester import SecurityTester

        prompts = request.get("prompts", [])
        if not prompts:
            return error_response(400, "prompts 必填")

        tester = SecurityTester()
        all_issues = []

        for prompt in prompts:
            report = tester.run_security_tests(prompt)
            issues = report.to_dict().get("issues", [])
            for issue in issues:
                issue["prompt"] = prompt
            all_issues.extend(issues)

        report_id = f"sec_{uuid.uuid4().hex[:8]}"
        overall_status = "safe" if len(all_issues) == 0 else "unsafe"

        return success_response(
            {
                "report_id": report_id,
                "prompt": f"{len(prompts)} prompts",
                "overall_status": overall_status,
                "issues": all_issues,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception as e:
        return error_response(500, f"安全扫描失败: {str(e)}")


@router.get("/report/{report_id}")
async def get_report(
    report_id: str,
    current_user: dict = Depends(PermissionDependency(Permission.VIEW_SECURITY_REPORT)),
) -> dict[str, Any]:
    """
    获取安全报告

    需要 VIEW_SECURITY_REPORT 权限。
    """
    try:
        from src.domain.security.security_tester import SecurityTester

        tester = SecurityTester()
        report = tester.get_report(report_id)

        if not report:
            return error_response(404, f"报告 '{report_id}' 不存在")

        return success_response(report.to_dict())
    except Exception as e:
        return error_response(500, f"获取报告失败: {str(e)}")


@router.get("/rules")
async def list_rules(
    current_user: dict = Depends(PermissionDependency(Permission.VIEW_SECURITY_REPORT)),
) -> dict[str, Any]:
    """
    获取安全规则列表

    需要 VIEW_SECURITY_REPORT 权限。
    """
    try:
        from src.domain.security.security_tester import SecurityTester

        tester = SecurityTester()
        rules = tester.get_rules()

        return success_response(
            [
                SecurityRuleResponse(
                    rule_id=rule.get("id"),
                    name=rule.get("name"),
                    pattern=rule.get("pattern"),
                    category=rule.get("category"),
                    severity=rule.get("severity"),
                    description=rule.get("description"),
                )
                for rule in rules
            ]
        )
    except Exception as e:
        return error_response(500, f"获取规则失败: {str(e)}")


@router.post("/rules")
async def add_rule(
    rule: SecurityRuleCreate,
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_SECURITY_RULES)),
) -> dict[str, Any]:
    """
    添加自定义安全规则

    需要 MANAGE_SECURITY_RULES 权限。
    """
    try:
        from src.domain.security.security_tester import SecurityTester

        tester = SecurityTester()
        new_rule = tester.add_rule(
            name=rule.name,
            pattern=rule.pattern,
            category=rule.category,
            severity=rule.severity,
            description=rule.description,
        )

        return success_response(
            {
                "rule_id": new_rule.get("id"),
                "name": new_rule.get("name"),
                "pattern": new_rule.get("pattern"),
                "category": new_rule.get("category"),
                "severity": new_rule.get("severity"),
                "description": new_rule.get("description"),
            }
        )
    except Exception as e:
        return error_response(500, f"添加规则失败: {str(e)}")


@router.delete("/rules/{rule_id}", status_code=status.HTTP_200_OK)
async def delete_rule(
    rule_id: str,
    current_user: dict = Depends(PermissionDependency(Permission.MANAGE_SECURITY_RULES)),
) -> dict[str, Any]:
    """
    删除安全规则

    需要 MANAGE_SECURITY_RULES 权限。
    """
    try:
        from src.domain.security.security_tester import SecurityTester

        tester = SecurityTester()
        success = tester.remove_rule(rule_id)

        if not success:
            return error_response(404, f"规则 '{rule_id}' 不存在")

        return success_response({"message": f"规则 '{rule_id}' 已删除"})
    except Exception as e:
        return error_response(500, f"删除规则失败: {str(e)}")


@router.get("/stats")
async def get_security_stats(
    current_user: dict = Depends(PermissionDependency(Permission.VIEW_SECURITY_REPORT)),
) -> dict[str, Any]:
    """
    获取安全统计

    需要 VIEW_SECURITY_REPORT 权限。
    """
    try:
        from src.domain.security.security_tester import SecurityTester

        tester = SecurityTester()
        stats = tester.get_stats()

        return success_response(stats)
    except Exception as e:
        return error_response(500, f"获取统计失败: {str(e)}")
