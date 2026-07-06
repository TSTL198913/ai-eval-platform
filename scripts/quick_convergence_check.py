"""快速收敛验证脚本 - 可配置样本数量"""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["TESTING"] = "1"

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

from src.domain.evaluators import auto_discover, list_core_evaluators
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.calibration.adaptive_calibrator import calibrator
from src.domain.golden_dataset import golden_dataset_manager
from src.domain.models.llm_factory import create_llm_client
from src.schemas.evaluation import EvaluationSchema

CONVERGENCE_THRESHOLD = 0.05
CORRELATION_THRESHOLD = 0.7
SAMPLE_LIMIT = int(os.environ.get("SAMPLE_LIMIT", "300"))


def main():
    auto_discover()
    golden_dataset_manager.load_datasets()

    llm_client = create_llm_client()
    print(f"LLM客户端: {type(llm_client).__name__}")

    core_evaluators = list_core_evaluators()
    results = []

    print(f"样本限制: {SAMPLE_LIMIT}")
    print(f"收敛阈值: mean_deviation < {CONVERGENCE_THRESHOLD*100:.1f}%, correlation > {CORRELATION_THRESHOLD}")
    print("-" * 80)

    for ev_name in core_evaluators:
        try:
            evaluator = EvaluatorFactory.get(ev_name, client=llm_client)
        except Exception as e:
            results.append({
                "evaluator": ev_name, "status": "error",
                "error": f"创建失败: {e}", "is_converged": False,
                "mean_deviation": None, "correlation": None,
            })
            print(f"{ev_name:20s} | ERROR: {e}")
            continue

        dataset = golden_dataset_manager.get_dataset_by_category(ev_name)
        if not dataset:
            dataset = golden_dataset_manager.get_dataset_by_category("general")
        if not dataset:
            results.append({
                "evaluator": ev_name, "status": "no_data",
                "is_converged": False, "mean_deviation": None, "correlation": None,
            })
            continue

        scored_samples = [s for s in dataset.samples if s.scores][:SAMPLE_LIMIT]
        if len(scored_samples) < 5:
            results.append({
                "evaluator": ev_name, "status": "insufficient_samples",
                "is_converged": False, "mean_deviation": None, "correlation": None,
            })
            continue

        original_samples = dataset.samples
        dataset.samples = scored_samples
        try:
            def _ev_func(sample):
                data = sample.input_data
                if isinstance(data, dict):
                    req = EvaluationSchema(id=sample.id, type=ev_name, payload=data)
                else:
                    req = data
                result = evaluator.safe_evaluate(req)
                return result.__dict__ if hasattr(result, "__dict__") else {"score": result}

            cal_result = calibrator.run_golden_calibration(
                evaluator_name=ev_name,
                evaluator_func=_ev_func,
                dataset_id=dataset.id,
            )
            md = cal_result.mean_deviation
            corr = cal_result.correlation
            converged = bool(md < CONVERGENCE_THRESHOLD and corr > CORRELATION_THRESHOLD)
            results.append({
                "evaluator": ev_name,
                "status": "evaluated",
                "n_samples": int(cal_result.n_samples),
                "mean_deviation": float(round(md, 4)),
                "correlation": float(round(corr, 4)),
                "is_converged": converged,
            })
            icon = "PASS" if converged else "FAIL"
            print(f"{ev_name:20s} | md={md*100:6.2f}% | corr={corr:.4f} | {icon}")
        except Exception as e:
            results.append({
                "evaluator": ev_name, "status": "eval_failed",
                "error": str(e), "is_converged": False,
                "mean_deviation": None, "correlation": None,
            })
            print(f"{ev_name:20s} | ERROR: {e}")
        finally:
            dataset.samples = original_samples

    converged_count = sum(1 for r in results if r["is_converged"])
    total = len(results)
    rate = converged_count / total * 100 if total > 0 else 0
    print("-" * 80)
    print(f"收敛结果: {converged_count}/{total} ({rate:.1f}%)")

    report = {
        "timestamp": datetime.now().isoformat(),
        "sample_limit": SAMPLE_LIMIT,
        "converged_count": converged_count,
        "total_evaluators": total,
        "convergence_rate": float(round(rate, 1)),
        "thresholds": {
            "mean_deviation_max": CONVERGENCE_THRESHOLD,
            "correlation_min": CORRELATION_THRESHOLD,
        },
        "results": results,
    }
    os.makedirs("data", exist_ok=True)
    with open("data/convergence_report_quick.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"报告已保存: data/convergence_report_quick.json")

    return 0 if converged_count == total else 1


if __name__ == "__main__":
    sys.exit(main())
