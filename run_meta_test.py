"""
运行元测试评估
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from src.domain.evaluators.meta_test_evaluator import MetaTestEvaluator
from src.schemas.evaluation import EvaluationSchema


def run_meta_test():
    test_file = os.path.join(os.path.dirname(__file__), "tests/unit/test_cost_governance.py")
    with open(test_file, encoding="utf-8") as f:
        test_code = f.read()

    request = EvaluationSchema(
        id="meta_test_cost_governance",
        type="meta_test",
        payload={"test_code": test_code, "test_results": None, "baseline_results": None},
    )

    evaluator = MetaTestEvaluator()
    result = evaluator.evaluate(request)

    print("=" * 70)
    print("元测试评估报告 - CostGovernance Test Suite (Mock 优化版)")
    print("=" * 70)
    print(f"\n总体评分: {result.score:.4f}")
    print(f"评估状态: {'通过' if result.is_valid else '失败'}")

    if result.data:
        print("\n" + "-" * 70)
        print("代码质量评分 (权重 0.3)")
        print("-" * 70)
        for k, v in result.data.get("code_quality", {}).items():
            print(f"  {k:25s}: {v:.4f}")
        print("\n" + "-" * 70)
        print("逻辑质量评分 (权重 0.4)")
        print("-" * 70)
        for k, v in result.data.get("logic_quality", {}).items():
            print(f"  {k:25s}: {v:.4f}")
        print("\n" + "-" * 70)
        print("漂移检测 (权重 0.3)")
        print("-" * 70)
        for k, v in result.data.get("drift_detection", {}).items():
            print(f"  {k:25s}: {v:.4f}")

    print("\n" + "=" * 70)
    return result


if __name__ == "__main__":
    run_meta_test()
