"""标注者一致性度量工具（Inter-Annotator Agreement Metrics）

2026工业级标准实现：
1. Cohen's Kappa - 双标注者一致性度量
2. Fleiss' Kappa - 多标注者一致性度量
3. Krippendorff's Alpha - 任意度量类型一致性度量

阈值标准：
- Cohen's Kappa ≥ 0.8: 优秀一致性
- Fleiss' Kappa ≥ 0.75: 优秀一致性
- Krippendorff's Alpha ≥ 0.80: 可靠性高
"""

from statistics import mean
from typing import Any


class AgreementMetrics:
    """标注者一致性度量工具类"""

    @staticmethod
    def cohens_kappa(annotator1: list[Any], annotator2: list[Any]) -> float:
        """计算 Cohen's Kappa（双标注者一致性度量）

        Args:
            annotator1: 标注者1的标注结果列表
            annotator2: 标注者2的标注结果列表

        Returns:
            Kappa值，范围[-1, 1]
        """
        if len(annotator1) != len(annotator2):
            raise ValueError("两个标注者的标注数量必须相同")

        n = len(annotator1)
        if n == 0:
            return 0.0

        categories = set(annotator1 + annotator2)
        category_counts: dict[Any, tuple[int, int]] = {}

        for cat in categories:
            category_counts[cat] = (0, 0)

        observed_agreements = 0

        for a1, a2 in zip(annotator1, annotator2, strict=False):
            category_counts[a1] = (category_counts[a1][0] + 1, category_counts[a1][1])
            category_counts[a2] = (category_counts[a2][0], category_counts[a2][1] + 1)

            if a1 == a2:
                observed_agreements += 1

        po = observed_agreements / n

        pe = 0.0
        for _cat, (count1, count2) in category_counts.items():
            pe += (count1 / n) * (count2 / n)

        if pe == 1.0:
            return 1.0

        kappa = (po - pe) / (1 - pe)
        return max(-1.0, min(1.0, kappa))

    @staticmethod
    def fleiss_kappa(annotations: list[list[Any]]) -> float:
        """计算 Fleiss' Kappa（多标注者一致性度量）

        Args:
            annotations: 标注矩阵，每行是一个样本的所有标注者标注结果

        Returns:
            Kappa值，范围[-1, 1]
        """
        if not annotations or len(annotations) == 0:
            return 0.0

        n_samples = len(annotations)
        n_annotators = len(annotations[0])

        all_categories = set()
        for sample_annotations in annotations:
            all_categories.update(sample_annotations)

        categories = list(all_categories)
        n_categories = len(categories)

        {cat: i for i, cat in enumerate(categories)}

        p_j_list = []

        for j in range(n_categories):
            total_j = 0
            for i in range(n_samples):
                total_j += annotations[i].count(categories[j])
            p_j = total_j / (n_samples * n_annotators)
            p_j_list.append(p_j)

        pe = sum(p_j**2 for p_j in p_j_list)

        p_i_list = []

        for i in range(n_samples):
            n_i_j_squared = 0
            for j in range(n_categories):
                n_i_j = annotations[i].count(categories[j])
                n_i_j_squared += n_i_j**2

            p_i = (n_i_j_squared - n_annotators) / (n_annotators * (n_annotators - 1))
            p_i_list.append(p_i)

        po = mean(p_i_list)

        if pe == 1.0:
            return 1.0

        kappa = (po - pe) / (1 - pe)
        return max(-1.0, min(1.0, kappa))

    @staticmethod
    def krippendorffs_alpha(annotations: list[list[Any]], metric_type: str = "interval") -> float:
        """计算 Krippendorff's Alpha（任意度量类型一致性度量）

        Args:
            annotations: 标注矩阵，每行是一个样本的所有标注者标注结果
            metric_type: 度量类型，可选: nominal, ordinal, interval, ratio

        Returns:
            Alpha值，范围[-1, 1]
        """
        if not annotations or len(annotations) == 0:
            return 0.0

        n_samples = len(annotations)
        n_annotators = len(annotations[0])

        total_pairs = n_samples * (n_annotators * (n_annotators - 1)) // 2

        if total_pairs == 0:
            return 0.0

        observed_disagreements = 0.0
        expected_disagreements = 0.0

        for i in range(n_samples):
            sample_annots = annotations[i]

            for a in range(n_annotators):
                for b in range(a + 1, n_annotators):
                    observed_disagreements += AgreementMetrics._distance(
                        sample_annots[a], sample_annots[b], metric_type
                    )

        all_annotations = [ann for sample in annotations for ann in sample]

        for a in range(len(all_annotations)):
            for b in range(a + 1, len(all_annotations)):
                expected_disagreements += AgreementMetrics._distance(
                    all_annotations[a], all_annotations[b], metric_type
                )

        n_all_annotations = len(all_annotations)
        expected_total_pairs = n_all_annotations * (n_all_annotations - 1) // 2

        if expected_total_pairs == 0:
            return 0.0

        do = observed_disagreements / total_pairs
        de = expected_disagreements / expected_total_pairs

        if de == 0:
            return 1.0

        alpha = 1 - (do / de)
        return max(-1.0, min(1.0, alpha))

    @staticmethod
    def _distance(a: Any, b: Any, metric_type: str) -> float:
        """计算两个标注之间的距离

        Args:
            a: 标注值a
            b: 标注值b
            metric_type: 度量类型

        Returns:
            距离值
        """
        if a == b:
            return 0.0

        if metric_type == "nominal":
            return 1.0

        elif metric_type == "ordinal":
            try:
                return abs(float(a) - float(b))
            except (ValueError, TypeError):
                return 1.0

        elif metric_type == "interval":
            try:
                return (float(a) - float(b)) ** 2
            except (ValueError, TypeError):
                return 1.0

        elif metric_type == "ratio":
            try:
                a_val = float(a)
                b_val = float(b)
                if a_val == 0 and b_val == 0:
                    return 0.0
                return ((a_val - b_val) / ((a_val + b_val) / 2)) ** 2 if a_val + b_val != 0 else 1.0
            except (ValueError, TypeError):
                return 1.0

        else:
            return 1.0

    @staticmethod
    def interpret_kappa(kappa: float) -> str:
        """解释 Kappa 值

        Args:
            kappa: Kappa值

        Returns:
            解释文本
        """
        if kappa >= 0.8:
            return "优秀一致性"
        elif kappa >= 0.61:
            return "良好一致性"
        elif kappa >= 0.41:
            return "中等一致性"
        elif kappa >= 0.01:
            return "较弱一致性"
        else:
            return "一致性不足"

    @staticmethod
    def interpret_alpha(alpha: float) -> str:
        """解释 Krippendorff's Alpha 值

        Args:
            alpha: Alpha值

        Returns:
            解释文本
        """
        if alpha >= 0.80:
            return "可靠性高"
        elif alpha >= 0.667:
            return "可靠性可接受"
        elif alpha >= 0.40:
            return "可靠性一般"
        else:
            return "需要改进"

    @staticmethod
    def calculate_all_metrics(annotations: list[list[Any]]) -> dict[str, float]:
        """计算所有一致性度量

        Args:
            annotations: 标注矩阵

        Returns:
            包含所有度量结果的字典
        """
        results = {}

        if len(annotations) >= 1 and len(annotations[0]) >= 2:
            if len(annotations[0]) == 2:
                annotator1 = [a[0] for a in annotations]
                annotator2 = [a[1] for a in annotations]
                results["cohens_kappa"] = AgreementMetrics.cohens_kappa(annotator1, annotator2)

            results["fleiss_kappa"] = AgreementMetrics.fleiss_kappa(annotations)
            results["krippendorffs_alpha_nominal"] = AgreementMetrics.krippendorffs_alpha(
                annotations, "nominal"
            )
            results["krippendorffs_alpha_interval"] = AgreementMetrics.krippendorffs_alpha(
                annotations, "interval"
            )

        return results
