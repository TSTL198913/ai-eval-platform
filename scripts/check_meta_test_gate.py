"""检查元测试质量门禁"""

import json
import sys
from pathlib import Path


def check_meta_test_gate():
    """检查元测试是否满足质量门禁"""
    # 加载元测试结果
    results_path = Path("meta_test_results.json")
    if not results_path.exists():
        print("⚠️ 元测试结果不存在,跳过质量门禁检查")
        print("提示: 运行 pytest tests/unit/test_meta_test_evaluator.py 生成元测试结果")
        return True  # 不阻止CI

    results = json.loads(results_path.read_text())

    # 检查质量门禁
    quality_gates = {
        "overall_score": 0.8,  # 总体评分≥80%
        "code_quality": 0.75,  # 代码质量≥75%
        "logic_quality": 0.80,  # 逻辑质量≥80%
        "drift_detection": 0.85,  # 漂移评分≥85%
    }

    passed = True
    failed_gates = []

    print("=" * 60)
    print("元测试质量门禁检查")
    print("=" * 60)

    for gate_name, threshold in quality_gates.items():
        actual_score = results.get(gate_name, 0.0)
        gate_passed = actual_score >= threshold

        status = "✅ 通过" if gate_passed else "❌ 未通过"
        print(f"{gate_name}: {actual_score:.2f} >= {threshold:.2f} {status}")

        if not gate_passed:
            passed = False
            failed_gates.append((gate_name, actual_score, threshold))

    print("=" * 60)

    if passed:
        print("✅ 所有质量门禁通过")
        print(f"元测试总体评分: {results.get('overall_score', 0.0):.2f}")
    else:
        print("❌ 质量门禁未通过")
        print(f"失败的门禁:")
        for gate_name, actual, threshold in failed_gates:
            print(f"  - {gate_name}: {actual:.2f} < {threshold:.2f}")
        print("\n建议:")
        print("  1. 查看元测试报告了解具体问题")
        print("  2. 根据建议改进测试代码")
        print("  3. 重新运行元测试验证改进效果")

    print()
    return passed


if __name__ == "__main__":
    passed = check_meta_test_gate()
    sys.exit(0 if passed else 1)
