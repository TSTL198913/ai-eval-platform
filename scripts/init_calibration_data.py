"""
校准数据集初始化脚本

初始化系统校准数据集，为各评估器建立基础校准曲线。

使用方法：
    python scripts/init_calibration_data.py

功能：
    1. 创建标准黄金数据集
    2. 导入预定义校准测试用例
    3. 执行基础校准并生成校准报告
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.domain.golden_dataset import golden_dataset_manager
from src.domain.calibration_service import calibration_service
from src.domain.adaptive_calibration import adaptive_calibrator
from tests.trustworthiness.calibration_dataset import get_all_calibration_data

CALIBRATION_CONFIG = {
    "default_threshold": 5.0,
    "min_calibration_samples": 5,
    "calibration_interval_hours": 24,
}


def create_standard_datasets():
    """创建标准黄金数据集"""
    datasets = [
        {
            "name": "通用评估校准集",
            "description": "用于通用评估器（LLM-as-Judge）的校准数据集，包含各种类型的问答样本",
            "category": "general",
        },
        {
            "name": "安全评估校准集",
            "description": "用于安全评估器的校准数据集，包含Prompt Injection、越狱、数据泄露等安全测试样本",
            "category": "security",
        },
        {
            "name": "代码评估校准集",
            "description": "用于代码评估器的校准数据集，包含各种代码质量测试样本",
            "category": "code",
        },
        {
            "name": "语义评估校准集",
            "description": "用于语义评估器的校准数据集，包含语义相似度测试样本",
            "category": "semantic",
        },
        {
            "name": "记忆评估校准集",
            "description": "用于记忆评估器的校准数据集，包含记忆检索和一致性测试样本",
            "category": "memory",
        },
        {
            "name": "工具调用校准集",
            "description": "用于工具调用评估器的校准数据集，包含工具选择和参数验证测试样本",
            "category": "function_call",
        },
    ]

    created_datasets = []
    for ds in datasets:
        existing = [d for d in golden_dataset_manager.list_datasets() if d.name == ds["name"]]
        if existing:
            print(f"[OK] 数据集 '{ds['name']}' 已存在 (ID: {existing[0].id})")
            created_datasets.append(existing[0])
        else:
            dataset = golden_dataset_manager.create_dataset(**ds)
            print(f"[NEW] 创建数据集 '{ds['name']}' (ID: {dataset.id})")
            created_datasets.append(dataset)

    return created_datasets


def import_calibration_test_cases(datasets):
    """导入预定义校准测试用例到数据集"""
    calibration_data = get_all_calibration_data()
    print(f"\n准备导入 {len(calibration_data)} 个校准测试用例")

    category_map = {
        "general": "通用评估校准集",
        "security": "安全评估校准集",
        "code": "代码评估校准集",
        "semantic": "语义评估校准集",
        "memory": "记忆评估校准集",
        "function_call": "工具调用校准集",
    }

    evaluator_category_map = {
        "llm_as_judge": "通用评估校准集",
        "security": "安全评估校准集",
        "code": "代码评估校准集",
        "semantic": "语义评估校准集",
        "memory": "记忆评估校准集",
        "function_call": "工具调用校准集",
    }

    imported_count = 0
    for test_case in calibration_data:
        target_name = evaluator_category_map.get(test_case.evaluator_type)
        if not target_name:
            print(f"[WARN] 未找到评估器 '{test_case.evaluator_type}' 的目标数据集")
            continue

        target_dataset = next((d for d in datasets if d.name == target_name), None)
        if not target_dataset:
            print(f"[WARN] 未找到数据集 '{target_name}'")
            continue

        scores = {}
        if test_case.ground_truth_score is not None:
            scores["overall"] = test_case.ground_truth_score
        if test_case.ground_truth_dimensions:
            scores.update(test_case.ground_truth_dimensions)

        sample_data = {
            "id": test_case.id,
            "user_input": test_case.input_text or "",
            "actual_output": test_case.actual_output or "",
            "expected_output": test_case.expected_output,
            "dimensions": list(test_case.ground_truth_dimensions.keys()) if test_case.ground_truth_dimensions else [],
            "scores": scores,
            "metadata": {
                "test_type": test_case.test_type,
                "confidence": test_case.confidence,
                "passing_threshold": test_case.passing_threshold,
                "evaluator_type": test_case.evaluator_type,
            },
        }

        sample = golden_dataset_manager.add_sample(target_dataset.id, sample_data)
        if sample:
            imported_count += 1

    print(f"[OK] 成功导入 {imported_count} 个校准测试用例")
    return imported_count


def run_basic_calibration():
    """执行基础校准"""
    print("\n执行基础校准...")

    datasets = golden_dataset_manager.list_datasets()
    for dataset in datasets:
        if len(dataset.samples) == 0:
            print(f"[WARN] 数据集 '{dataset.name}' 无样本，跳过校准")
            continue

        print(f"\n--- 校准数据集: {dataset.name} (ID: {dataset.id}) ---")

        def mock_evaluator(sample):
            """模拟评估器 - 返回黄金分数作为预测（理想情况）"""
            if sample.scores:
                return {"score": sum(sample.scores.values()) / len(sample.scores)}
            return {"score": 0.5}

        try:
            result = adaptive_calibrator.run_calibration(
                evaluator_name=f"mock_{dataset.category}",
                evaluator_func=mock_evaluator,
                dataset_id=dataset.id,
                threshold=CALIBRATION_CONFIG["default_threshold"],
            )
            print(f"校准结果: {'通过' if result.is_calibrated else '未通过'}")
            print(f"   样本数: {result.n_samples}")
            print(f"   平均偏差: {result.mean_deviation:.4f}")
            print(f"   RMSE: {result.rmse:.4f}")
            print(f"   相关性: {result.correlation:.4f}")
            for suggestion in result.suggestions:
                print(f"   [INFO] {suggestion}")
        except Exception as e:
            print(f"[ERROR] 校准失败: {e}")


def export_calibration_summary():
    """导出校准摘要"""
    summary = {
        "config": CALIBRATION_CONFIG,
        "datasets": [],
        "timestamp": "2026-01-01T00:00:00Z",
    }

    for dataset in golden_dataset_manager.list_datasets():
        stats = golden_dataset_manager.get_sample_statistics(dataset.id)
        summary["datasets"].append({
            "id": dataset.id,
            "name": dataset.name,
            "description": dataset.description,
            "category": dataset.category,
            "total_samples": stats.get("total_samples", 0),
            "corrected_samples": stats.get("corrected_samples", 0),
            "corrected_ratio": stats.get("corrected_ratio", 0),
            "avg_score": stats.get("avg_score", 0),
            "conflict_samples": stats.get("conflict_samples", 0),
        })

    output_dir = "data/calibration"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "calibration_summary.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n校准摘要已导出到: {output_path}")
    return summary


def main():
    """主函数"""
    print("=" * 70)
    print("         校准数据集初始化脚本")
    print("=" * 70)

    print("\n[步骤1] 创建标准黄金数据集")
    datasets = create_standard_datasets()

    print("\n[步骤2] 导入校准测试用例")
    import_calibration_test_cases(datasets)

    print("\n[步骤3] 执行基础校准")
    run_basic_calibration()

    print("\n[步骤4] 导出校准摘要")
    export_calibration_summary()

    print("\n" + "=" * 70)
    print("         校准数据集初始化完成!")
    print("=" * 70)

    print("\n数据集统计:")
    for dataset in golden_dataset_manager.list_datasets():
        stats = golden_dataset_manager.get_sample_statistics(dataset.id)
        print(f"  - {dataset.name}: {stats.get('total_samples', 0)} 个样本")


if __name__ == "__main__":
    main()