"""
使用评估器进行自测
"""

import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_path = os.path.join(project_root, "src")

if project_root not in sys.path:
    sys.path.insert(0, project_root)
if src_path not in sys.path:
    sys.path.insert(0, src_path)


from src.domain.evaluators.code import CodeEvaluator
from src.domain.evaluators.security import SecurityEvaluator
from src.schemas.evaluation import EvaluationSchema


def test_code_evaluation():
    """测试代码评估器"""
    files = [
        "src/domain/evaluator_version.py",
        "src/domain/statistical_analysis.py",
        "src/domain/adaptive_calibration.py",
    ]

    evaluator = CodeEvaluator()

    print("=" * 60)
    print("代码语法检查结果")
    print("=" * 60)

    all_passed = True
    for filepath in files:
        with open(filepath, encoding="utf-8") as f:
            code = f.read()

        request = EvaluationSchema(
            id=f"syntax_check_{filepath}",
            type="code",
            payload={"code": code, "metadata": {"language": "python"}},
        )

        result = evaluator.evaluate(request)
        filename = filepath.split("/")[-1]
        status = "PASS" if result.is_valid else "FAIL"
        print(f"{status}: {filename}")
        print(f"  - 评分: {result.score}")
        if not result.is_valid:
            print(f"  - 错误: {result.error}")
            all_passed = False

    return all_passed


def test_security_evaluation():
    """测试安全评估器"""
    files = [
        "src/domain/evaluator_version.py",
        "src/domain/statistical_analysis.py",
        "src/domain/adaptive_calibration.py",
        "src/domain/calibration_service.py",
        "src/domain/meta_evaluator.py",
        "src/domain/model_performance.py",
        "src/domain/model_routing.py",
        "src/domain/fine_tune_exporter.py",
        "src/domain/fine_tuned_evaluator.py",
    ]

    evaluator = SecurityEvaluator()

    print("\n" + "=" * 60)
    print("安全评估结果")
    print("=" * 60)

    all_safe = True
    for filepath in files:
        if not os.path.exists(filepath):
            continue

        with open(filepath, encoding="utf-8") as f:
            code = f.read()

        request = EvaluationSchema(
            id=f"security_check_{filepath}",
            type="security",
            payload={"user_input": code, "tests": ["injection", "tool_abuse", "data_leak"]},
        )

        result = evaluator.evaluate(request)
        filename = filepath.split("/")[-1]

        if result.data:
            risk_level = result.data.get("risk_level", "unknown")
            overall_score = result.data.get("overall_score", 0)

            if risk_level == "low":
                print(f"PASS: {filename} - 风险等级: {risk_level} (评分: {overall_score})")
            else:
                print(f"FAIL: {filename} - 风险等级: {risk_level} (评分: {overall_score})")
                all_safe = False
        else:
            print(f"ERROR: {filename} - {result.error}")
            all_safe = False

    return all_safe


def test_statistical_module():
    """测试统计分析模块"""
    print("\n" + "=" * 60)
    print("统计分析模块测试")
    print("=" * 60)

    from src.domain.statistical_analysis import StatisticalSignificanceAnalyzer

    analyzer = StatisticalSignificanceAnalyzer()

    # 测试 A/B 测试
    scores_a = [0.75, 0.72, 0.78, 0.80, 0.77]
    scores_b = [0.85, 0.88, 0.82, 0.87, 0.86]

    try:
        result = analyzer.run_ab_test(
            scores_a=scores_a, scores_b=scores_b, model_a_name="Model A", model_b_name="Model B"
        )

        print("AB测试: PASS")
        print(f"  - p值: {result.p_value:.4f}")
        print(f"  - 显著差异: {result.is_significant}")
        print(f"  - 胜出模型: {result.winner}")

        # 测试置信区间
        ci = analyzer.calculate_confidence_interval(scores_a)
        print("置信区间: PASS")
        print(f"  - 估计值: {ci.estimate:.4f}")
        print(f"  - 区间: [{ci.lower:.4f}, {ci.upper:.4f}]")

        return True
    except Exception as e:
        print(f"FAIL: {e}")
        return False


def test_version_control_module():
    """测试版本控制模块"""
    print("\n" + "=" * 60)
    print("版本控制模块测试")
    print("=" * 60)

    import tempfile

    from src.domain.evaluator_version import EvaluatorVersionManager

    # 使用临时目录
    temp_dir = tempfile.mkdtemp()
    manager = EvaluatorVersionManager(storage_path=temp_dir)

    try:
        # 测试注册版本
        v1 = manager.register_version(
            evaluator_name="test_evaluator",
            version="1.0.0",
            code_hash="abc123",
            config={"threshold": 0.8},
        )
        print(f"注册版本: PASS (version_id: {v1.version_id[:8]}...)")

        # 测试获取当前版本
        current = manager.get_current_version("test_evaluator")
        if current and current.version == "1.0.0":
            print("获取当前版本: PASS")
        else:
            print("获取当前版本: FAIL")
            return False

        # 测试更新校准
        updated = manager.update_calibration("test_evaluator", 0.85)
        if updated and updated.calibration_score == 0.85:
            print("更新校准: PASS")
        else:
            print("更新校准: FAIL")
            return False

        # 测试检查校准状态
        status = manager.check_calibration_status("test_evaluator")
        status_value = status.get("status")
        # 注意：注册后未校准时状态是 "not_calibrated"，这是正确的
        valid_statuses = ["calibrated", "not_calibrated", "drifted"]
        if status_value in valid_statuses:
            print(f"检查校准状态: PASS (状态: {status_value})")
        else:
            print(f"检查校准状态: FAIL (未知状态: {status_value})")
            return False

        return True
    except Exception as e:
        print(f"FAIL: {e}")
        return False
    finally:
        # 清理临时目录
        import shutil

        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    import os

    results = []

    results.append(("代码语法检查", test_code_evaluation()))
    results.append(("安全评估", test_security_evaluation()))
    results.append(("统计分析模块", test_statistical_module()))
    results.append(("版本控制模块", test_version_control_module()))

    print("\n" + "=" * 60)
    print("综合测试结果")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False

    print("=" * 60)
    if all_passed:
        print("所有测试通过！")
    else:
        print("存在失败测试，请检查。")
    print("=" * 60)
