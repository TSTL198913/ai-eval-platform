"""分析黄金数据集统计特性"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["TESTING"] = "1"

from src.domain.golden_dataset import golden_dataset_manager


def main():
    golden_dataset_manager.load_datasets()
    datasets = golden_dataset_manager.list_datasets()

    print("=" * 80)
    print("黄金数据集统计特性分析")
    print("=" * 80)
    print(f"数据集总数: {len(datasets)}")
    print()

    all_valid = True
    dataset_stats = []

    for ds in datasets:
        scored_samples = [s for s in ds.samples if s.scores]
        if not scored_samples:
            print(f"{ds.name:20s} | category={ds.category} | 无标注样本")
            all_valid = False
            continue

        all_scores = []
        for s in scored_samples:
            all_scores.extend(list(s.scores.values()))

        n_samples = len(scored_samples)
        n_scores = len(all_scores)
        min_score = min(all_scores)
        max_score = max(all_scores)
        avg_score = sum(all_scores) / n_scores
        variance = sum((s - avg_score) ** 2 for s in all_scores) / n_scores if n_scores > 1 else 0
        std_dev = variance ** 0.5
        unique_scores = len(set(all_scores))
        has_meaninful_range = (max_score - min_score) > 0.01

        print(f"{ds.name:20s} | category={ds.category}")
        print(f"  总样本: {len(ds.samples)}, 有评分: {n_samples}, 评分总数: {n_scores}")
        print(f"  分数范围: [{min_score:.3f}, {max_score:.3f}]")
        print(f"  平均分: {avg_score:.3f}, 标准差: {std_dev:.3f}")
        print(f"  不同分值数: {unique_scores}")
        print(f"  有效评分范围: {'是' if has_meaninful_range else '否'}")
        print()

        dataset_stats.append({
            "name": ds.name,
            "category": ds.category,
            "total_samples": len(ds.samples),
            "scored_samples": n_samples,
            "min_score": min_score,
            "max_score": max_score,
            "avg_score": avg_score,
            "std_dev": std_dev,
            "unique_scores": unique_scores,
            "has_meaninful_range": has_meaninful_range,
        })

    print("=" * 80)
    print("结论分析")
    print("=" * 80)
    for ds in datasets:
        scored_samples = [s for s in ds.samples if s.scores]
        if not scored_samples:
            print(f"⚠️ {ds.name} 无标注样本，无法用于收敛验证")
            all_valid = False
            continue
        all_scores = []
        for s in scored_samples:
            all_scores.extend(list(s.scores.values()))
        if len(set(all_scores)) <= 1:
            print(f"⚠️ {ds.name} 评分全部相同，方差为0，无法评估相关性")
            all_valid = False

    if all_valid:
        print("✅ 所有黄金数据集数据质量有效")
    else:
        print("❌ 部分数据集数据质量存在问题")

    return 0 if all_valid else 1


if __name__ == "__main__":
    sys.exit(main())
