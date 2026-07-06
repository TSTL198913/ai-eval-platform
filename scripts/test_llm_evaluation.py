"""测试LLM评估效果"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["TESTING"] = "1"

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

from src.domain.evaluators import auto_discover
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.golden_dataset import golden_dataset_manager
from src.domain.models.llm_factory import create_llm_client
from src.schemas.evaluation import EvaluationSchema, EvaluatorStatus


def main():
    auto_discover()
    golden_dataset_manager.load_datasets()

    llm_client = create_llm_client()
    print("LLM客户端:", type(llm_client).__name__)

    # 获取 general 评估器和数据集
    evaluator = EvaluatorFactory.get("general", client=llm_client)
    dataset = golden_dataset_manager.get_dataset_by_category("general")

    print("=== LLM评估测试 ===")
    print("评估器类型:", type(evaluator).__name__)
    print("数据集:", dataset.name)
    print("样本数:", len(dataset.samples))

    # 测试前5个样本
    print()
    print("=== 测试前5个样本 ===")
    total_score_diff = 0.0
    n_valid = 0

    for i, sample in enumerate(dataset.samples[:5]):
        request = EvaluationSchema(
            id=sample.id,
            type="general",
            payload=sample.input_data,
        )

        result = evaluator.evaluate(request)
        gold_score = sample.scores.get("overall", sample.scores.get("correctness", 0.0))
        eval_score = result.score or 0.0

        print(f"\n样本 {i+1}:")
        print(f"  ID: {sample.id}")
        print(f"  用户输入: {sample.user_input[:50]}..." if len(sample.user_input) > 50 else f"  用户输入: {sample.user_input}")
        print(f"  黄金分数: {gold_score:.4f}")
        print(f"  评估分数: {eval_score:.4f}")
        print(f"  偏差: {abs(gold_score - eval_score):.4f}")
        print(f"  状态: {result.evaluation_status}")
        raw_output = result.data.get("raw_output", "") if result.data else ""
        if raw_output:
            print(f"  LLM原始输出: {raw_output[:100]}...")

        if result.score is not None:
            total_score_diff += abs(gold_score - eval_score)
            n_valid += 1

    if n_valid > 0:
        avg_diff = total_score_diff / n_valid
        print(f"\n=== 平均偏差: {avg_diff:.4f} ({avg_diff*100:.2f}%) ===")
        if avg_diff < 0.05:
            print("✅ 偏差在可接受范围内")
        else:
            print("❌ 偏差超过阈值")

    return 0


if __name__ == "__main__":
    sys.exit(main())
