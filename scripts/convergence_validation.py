"""评估器收敛验证脚本

检查所有核心评估器是否达到收敛标准：
- mean_deviation < 5%
- correlation > 0.7

执行步骤：
1. 加载黄金数据集
2. 对每个核心评估器运行校准验证
3. 检查收敛指标
4. 生成收敛报告
"""

import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

from src.domain.evaluators import list_core_evaluators, auto_discover
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.calibration.adaptive_calibrator import calibrator
from src.domain.golden_dataset import golden_dataset_manager
from src.domain.models.llm_factory import create_llm_client


CONVERGENCE_THRESHOLD = 0.05
CORRELATION_THRESHOLD = 0.7


def load_golden_dataset() -> None:
    """加载黄金数据集"""
    golden_dataset_manager.load_datasets()
    datasets = golden_dataset_manager.list_datasets()
    print(f"已加载 {len(datasets)} 个黄金数据集")
    for ds in datasets:
        scored_samples = sum(1 for s in ds.samples if s.scores)
        print(f"  - {ds.name} (category: {ds.category}, samples: {len(ds.samples)}, scored: {scored_samples})")


def evaluate_evaluator_convergence(evaluator_name: str, llm_client=None) -> Tuple[bool, Dict[str, Any]]:
    """评估单个评估器的收敛状态
    
    Returns:
        (是否收敛, 详细信息)
    """
    try:
        evaluator = EvaluatorFactory.get(evaluator_name, client=llm_client)
    except Exception as e:
        return False, {
            "evaluator": evaluator_name,
            "status": "error",
            "error": f"评估器创建失败: {str(e)}",
            "mean_deviation": None,
            "correlation": None,
            "is_converged": False,
        }

    dataset = golden_dataset_manager.get_dataset_by_category(evaluator_name)
    if not dataset:
        dataset = golden_dataset_manager.get_dataset_by_category("general")
    
    if not dataset:
        return False, {
            "evaluator": evaluator_name,
            "status": "no_data",
            "error": "没有可用的黄金数据集",
            "mean_deviation": None,
            "correlation": None,
            "is_converged": False,
        }

    scored_samples = [s for s in dataset.samples if s.scores]
    if len(scored_samples) < 5:
        return False, {
            "evaluator": evaluator_name,
            "status": "insufficient_samples",
            "error": f"标注样本不足 (需要至少5个，当前{len(scored_samples)}个)",
            "mean_deviation": None,
            "correlation": None,
            "is_converged": False,
        }

    try:
        from src.schemas.evaluation import EvaluationSchema

        def _evaluator_func(sample):
            """将 GoldenSample 转换为 EvaluationSchema 后评估"""
            data = sample.input_data
            if isinstance(data, dict):
                request = EvaluationSchema(
                    id=sample.id,
                    type=evaluator_name,
                    payload=data,
                )
            else:
                request = data
            result = evaluator.safe_evaluate(request)
            return result.__dict__ if hasattr(result, "__dict__") else {"score": result}

        result = calibrator.run_golden_calibration(
            evaluator_name=evaluator_name,
            evaluator_func=_evaluator_func,
            dataset_id=dataset.id,
        )

        mean_deviation = result.mean_deviation
        correlation = result.correlation
        is_converged = bool(mean_deviation < CONVERGENCE_THRESHOLD and correlation > CORRELATION_THRESHOLD)

        return is_converged, {
            "evaluator": evaluator_name,
            "status": "evaluated",
            "dataset": dataset.name,
            "n_samples": int(result.n_samples),
            "mean_deviation": float(round(mean_deviation, 4)),
            "correlation": float(round(correlation, 4)),
            "rmse": float(round(result.rmse, 4)),
            "max_deviation": float(round(result.max_deviation, 4)),
            "mean_gold": float(round(result.mean_gold, 4)),
            "mean_eval": float(round(result.mean_eval, 4)),
            "is_converged": is_converged,
            "suggestions": list(result.suggestions),
        }

    except Exception as e:
        return False, {
            "evaluator": evaluator_name,
            "status": "evaluation_failed",
            "error": f"评估执行失败: {str(e)}",
            "mean_deviation": None,
            "correlation": None,
            "is_converged": False,
        }


def generate_convergence_report(results: List[Dict[str, Any]]) -> str:
    """生成收敛验证报告"""
    converged_count = sum(1 for r in results if r["is_converged"])
    total_count = len(results)
    pass_rate = converged_count / total_count * 100

    lines = [
        "=" * 80,
        "评估器收敛验证报告",
        "=" * 80,
        f"验证时间: {datetime.now().isoformat()}",
        f"收敛阈值: mean_deviation < {CONVERGENCE_THRESHOLD * 100:.1f}%, correlation > {CORRELATION_THRESHOLD}",
        f"评估器总数: {total_count}",
        f"已收敛: {converged_count}",
        f"未收敛: {total_count - converged_count}",
        f"收敛率: {pass_rate:.1f}%",
        "",
        "=" * 80,
        "",
    ]

    lines.append("详细结果:")
    for result in results:
        status_icon = "✓" if result["is_converged"] else "✗"
        lines.append(f"\n  {status_icon} {result['evaluator']}:")
        lines.append(f"     状态: {result['status']}")
        
        if result.get("mean_deviation") is not None:
            deviation_status = "通过" if result["mean_deviation"] < CONVERGENCE_THRESHOLD else "未通过"
            lines.append(f"     平均偏差: {result['mean_deviation']*100:.2f}% ({deviation_status})")
        
        if result.get("correlation") is not None:
            corr_status = "通过" if result["correlation"] > CORRELATION_THRESHOLD else "未通过"
            lines.append(f"     相关性: {result['correlation']:.4f} ({corr_status})")
        
        if result.get("rmse") is not None:
            lines.append(f"     RMSE: {result['rmse']:.4f}")
        
        if "dataset" in result:
            lines.append(f"     数据集: {result['dataset']}")
        
        if "n_samples" in result:
            lines.append(f"     样本数: {result['n_samples']}")
        
        if "error" in result:
            lines.append(f"     错误: {result['error']}")
        
        if "suggestions" in result and result["suggestions"]:
            lines.append(f"     建议: {', '.join(result['suggestions'][:3])}")

    lines.append("\n" + "=" * 80)
    
    if converged_count == total_count:
        lines.append("🎉 所有评估器均已达到收敛标准！")
    else:
        lines.append(f"⚠️  {total_count - converged_count} 个评估器未达到收敛标准，需要进一步优化")

    lines.append("=" * 80)
    return "\n".join(lines)


def main():
    """主入口"""
    print("启动评估器收敛验证...")
    print()

    auto_discover()

    load_golden_dataset()
    print()

    llm_client = create_llm_client()
    print(f"LLM客户端: {type(llm_client).__name__}")
    print()

    core_evaluators = list_core_evaluators()
    print(f"核心评估器列表 ({len(core_evaluators)}个):")
    print(f"  {', '.join(core_evaluators)}")
    print()

    results = []
    for evaluator_name in core_evaluators:
        print(f"正在验证: {evaluator_name}...")
        is_converged, detail = evaluate_evaluator_convergence(evaluator_name, llm_client)
        results.append(detail)
        status = "✓ 已收敛" if is_converged else "✗ 未收敛"
        if detail["mean_deviation"] is not None:
            print(f"  结果: {status} | 偏差={detail['mean_deviation']*100:.2f}% | 相关={detail['correlation']:.4f}")
        else:
            print(f"  结果: {status} | {detail.get('error', '未知错误')}")
        print()

    report = generate_convergence_report(results)
    print(report)

    report_file = f"data/convergence_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    os.makedirs(os.path.dirname(report_file), exist_ok=True)
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n报告已保存到: {report_file}")

    converged_count = sum(1 for r in results if r["is_converged"])
    return 0 if converged_count == len(core_evaluators) else 1


if __name__ == "__main__":
    sys.exit(main())