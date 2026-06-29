"""
元测试脚本 - 测试自己的测试代码
使用系统自身的评估器来评估测试代码质量
"""

import os
import sys

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.schemas.evaluation import EvaluationSchema


def evaluate_test_file_with_system(test_file_path: str):
    """
    使用系统评估器评估测试文件质量
    """
    with open(test_file_path, encoding="utf-8") as f:
        test_code = f.read()

    results = {}

    # 1. CodeEvaluator - 语法和代码质量
    print("=" * 60)
    print(f"[EVAL] 评估测试文件: {os.path.basename(test_file_path)}")
    print("=" * 60)

    from src.domain.evaluators.code import CodeEvaluator

    try:
        code_evaluator = CodeEvaluator()
        code_result = code_evaluator.evaluate(
            EvaluationSchema(
                id="meta_code",
                type="code",
                payload={"code": test_code},
                metadata={"language": "python"},
            )
        )
        results["code_quality"] = {
            "score": code_result.score,
            "is_valid": code_result.is_valid,
            "error": code_result.error,
            "metadata": code_result.metadata,
        }
        print("\n[CODE] CodeEvaluator 结果:")
        print(f"   - 语法有效: {code_result.metadata.get('syntax_valid', 'N/A')}")
        print(f"   - 评分: {code_result.score:.2f}")
        if code_result.error:
            print(f"   - 错误: {code_result.error}")
    except Exception as e:
        results["code_quality"] = {"error": str(e)}
        print(f"\n[ERROR] CodeEvaluator 失败: {e}")

    # 2. SecurityEvaluator - 安全检测
    print("\n" + "-" * 60)
    from src.domain.evaluators.security import SecurityEvaluator

    try:
        security_evaluator = SecurityEvaluator()
        security_result = security_evaluator.evaluate(
            EvaluationSchema(
                id="meta_security",
                type="security",
                payload={"user_input": test_code, "tests": ["injection", "data_leak"]},
            )
        )
        results["security"] = {
            "risk_level": security_result.data.get("risk_level"),
            "injection_detected": security_result.data.get("security_tests", {})
            .get("injection", {})
            .get("detected"),
            "data_leak_detected": security_result.data.get("security_tests", {})
            .get("data_leak", {})
            .get("detected"),
            "score": security_result.score,
        }
        print("\n[SECURITY] SecurityEvaluator 结果:")
        print(f"   - 风险等级: {security_result.data.get('risk_level', 'N/A')}")
        print(
            f"   - 注入攻击检测: {security_result.data.get('security_tests', {}).get('injection', {}).get('detected', 'N/A')}"
        )
        print(
            f"   - 数据泄露检测: {security_result.data.get('security_tests', {}).get('data_leak', {}).get('detected', 'N/A')}"
        )
    except Exception as e:
        results["security"] = {"error": str(e)}
        print(f"\n[ERROR] SecurityEvaluator 失败: {e}")

    # 3. GrammarEvaluator - 语法检查
    print("\n" + "-" * 60)
    try:
        from src.domain.evaluators.grammar import GrammarEvaluator

        grammar_evaluator = GrammarEvaluator()
        grammar_result = grammar_evaluator.evaluate(
            EvaluationSchema(
                id="meta_grammar",
                type="grammar",
                payload={"text": test_code},
                metadata={"language": "python"},
            )
        )
        results["grammar"] = {
            "score": grammar_result.score,
            "is_valid": grammar_result.is_valid,
            "data": grammar_result.data,
        }
        print("\n[GRAMMAR] GrammarEvaluator 结果:")
        print(f"   - 语法正确: {grammar_result.is_valid}")
        print(f"   - 评分: {grammar_result.score:.2f}")
    except Exception as e:
        results["grammar"] = {"error": str(e)}
        print(f"\n[WARNING] GrammarEvaluator 失败: {e}")

    return results


def check_test_completeness(test_file_path: str):
    """
    检查测试用例的完整性
    """
    with open(test_file_path, encoding="utf-8") as f:
        test_code = f.read()

    findings = {
        "test_classes": 0,
        "test_methods": 0,
        "positive_cases": 0,
        "negative_cases": 0,
        "boundary_cases": 0,
        "mock_usage": 0,
        "assertions": 0,
        "issues": [],
    }

    import re

    # 统计测试类
    test_classes = re.findall(r"class (Test\w+)", test_code)
    findings["test_classes"] = len(test_classes)

    # 统计测试方法
    test_methods = re.findall(r"def (test_\w+)", test_code)
    findings["test_methods"] = len(test_methods)

    # 统计场景类型
    findings["positive_cases"] = len(re.findall(r"class.*Positive", test_code))
    findings["negative_cases"] = len(re.findall(r"class.*Negative", test_code))
    findings["boundary_cases"] = len(re.findall(r"class.*Boundary", test_code))

    # 统计 Mock 使用
    findings["mock_usage"] = len(re.findall(r"(Mock|MagicMock|patch)", test_code))

    # 统计断言
    findings["assertions"] = len(re.findall(r"assert\s+", test_code))

    # 检查问题
    if findings["test_classes"] == 0:
        findings["issues"].append("FAIL: 没有找到测试类")
    if findings["test_methods"] < 10:
        findings["issues"].append(f"WARN: 测试方法数量较少: {findings['test_methods']}")
    if findings["positive_cases"] == 0:
        findings["issues"].append("WARN: 缺少正向测试类")
    if findings["negative_cases"] == 0:
        findings["issues"].append("WARN: 缺少负向测试类")
    if findings["boundary_cases"] == 0:
        findings["issues"].append("WARN: 缺少边界测试类")
    if findings["mock_usage"] == 0:
        findings["issues"].append("WARN: 没有使用 Mock")
    if findings["assertions"] < findings["test_methods"]:
        findings["issues"].append(
            f"WARN: 断言数量({findings['assertions']})少于测试方法({findings['test_methods']})"
        )

    print("\n[COMPLETENESS] 测试完整性检查:")
    print(f"   - 测试类数量: {findings['test_classes']}")
    print(f"   - 测试方法数量: {findings['test_methods']}")
    print(f"   - 正向测试类: {findings['positive_cases']}")
    print(f"   - 负向测试类: {findings['negative_cases']}")
    print(f"   - 边界测试类: {findings['boundary_cases']}")
    print(f"   - Mock 使用次数: {findings['mock_usage']}")
    print(f"   - 断言数量: {findings['assertions']}")

    if findings["issues"]:
        print("\n发现的问题:")
        for issue in findings["issues"]:
            print(f"   {issue}")

    return findings


def run_all_meta_tests():
    """
    运行所有元测试
    """
    test_files = [
        "tests/unit/test_statistical_analysis.py",
        "tests/unit/test_golden_dataset.py",
        "tests/unit/test_evaluator_version.py",
        "tests/unit/test_evaluator_factory.py",
        "tests/unit/test_circuit_breaker.py",
    ]

    all_results = {}

    print("\n" + "=" * 70)
    print("[START] 开始元测试 - 使用系统评估器评估测试代码质量")
    print("=" * 70)

    for test_file in test_files:
        if os.path.exists(test_file):
            print(f"\n\n{'=' * 70}")
            print(f"[FILE] 评估文件: {test_file}")
            print("=" * 70)

            # 使用系统评估器评估
            results = evaluate_test_file_with_system(test_file)

            # 检查测试完整性
            completeness = check_test_completeness(test_file)

            all_results[test_file] = {
                "evaluation_results": results,
                "completeness": completeness,
            }
        else:
            print(f"\n[WARNING] 文件不存在: {test_file}")

    # 汇总报告
    print("\n\n" + "=" * 70)
    print("[SUMMARY] 元测试汇总报告")
    print("=" * 70)

    for file_path, results in all_results.items():
        print(f"\n[FILE] {os.path.basename(file_path)}")

        # 代码质量
        code_q = results["evaluation_results"].get("code_quality", {})
        if "error" not in code_q:
            print(f"   代码质量: {code_q.get('score', 'N/A'):.2f}")

        # 安全性
        security = results["evaluation_results"].get("security", {})
        if "error" not in security:
            risk = security.get("risk_level", "N/A")
            risk_icon = "PASS" if risk == "low" else "WARN" if risk == "medium" else "FAIL"
            print(f"   安全风险: [{risk_icon}] {risk}")

        # 完整性
        comp = results["completeness"]
        test_count = comp.get("test_methods", 0)
        issues_count = len(comp.get("issues", []))
        quality = "PASS" if issues_count == 0 else "WARN" if issues_count < 3 else "FAIL"
        print(f"   测试数量: {test_count}")
        print(f"   完整性: [{quality}] ({test_count - issues_count}/{test_count})")

    return all_results


if __name__ == "__main__":
    results = run_all_meta_tests()
