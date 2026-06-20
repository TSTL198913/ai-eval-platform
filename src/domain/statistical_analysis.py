"""
统计显著性验证模块
使用 t-test 和 Mann-Whitney U 检验确保模型能力提升的统计显著性
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import numpy as np
from scipy import stats


class SignificanceLevel(Enum):
    P05 = 0.05  # 95% 置信度
    P01 = 0.01  # 99% 置信度
    P10 = 0.10  # 90% 置信度


@dataclass
class ABTestResult:
    """A/B 测试结果"""

    model_a_name: str
    model_b_name: str
    n_samples: int

    # 基本统计
    mean_a: float
    mean_b: float
    std_a: float
    std_b: float

    # 显著性检验
    t_statistic: float
    p_value: float
    is_significant: bool
    significance_level: float

    # 效应量
    effect_size: float  # Cohen's d
    effect_interpretation: str  # small/medium/large

    # 置信区间
    ci_lower: float
    ci_upper: float
    ci_confidence: float

    # 结论
    winner: str  # "model_a" / "model_b" / "no_significant_difference"
    conclusion: str

    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_a_name": self.model_a_name,
            "model_b_name": self.model_b_name,
            "n_samples": self.n_samples,
            "mean_a": round(self.mean_a, 4),
            "mean_b": round(self.mean_b, 4),
            "std_a": round(self.std_a, 4),
            "std_b": round(self.std_b, 4),
            "t_statistic": round(self.t_statistic, 4),
            "p_value": self.p_value,
            "is_significant": self.is_significant,
            "significance_level": self.significance_level,
            "effect_size": round(self.effect_size, 4),
            "effect_interpretation": self.effect_interpretation,
            "ci_lower": round(self.ci_lower, 4),
            "ci_upper": round(self.ci_upper, 4),
            "ci_confidence": self.ci_confidence,
            "winner": self.winner,
            "conclusion": self.conclusion,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ConfidenceInterval:
    """置信区间"""

    estimate: float
    lower: float
    upper: float
    confidence: float  # 0.95 = 95%
    method: str  # "bootstrap" / "t-distribution"

    def to_dict(self) -> dict[str, Any]:
        return {
            "estimate": round(self.estimate, 4),
            "lower": round(self.lower, 4),
            "upper": round(self.upper, 4),
            "confidence": self.confidence,
            "interval_width": round(self.upper - self.lower, 4),
            "method": self.method,
        }


class StatisticalSignificanceAnalyzer:
    """统计显著性分析器"""

    def __init__(self, bootstrap_iterations: int = 10000, random_seed: int = 42):
        self._bootstrap_iterations = bootstrap_iterations
        self._random_seed = random_seed

    def run_ab_test(
        self,
        scores_a: list[float],
        scores_b: list[float],
        model_a_name: str = "Model A",
        model_b_name: str = "Model B",
        significance_level: float = 0.05,
        test_type: str = "auto",
    ) -> ABTestResult:
        """运行 A/B 测试

        Args:
            scores_a: A组分数列表
            scores_b: B组分数列表
            model_a_name: A模型名称
            model_b_name: B模型名称
            significance_level: 显著性水平 (默认0.05)
            test_type: "auto" / "ttest" / "mannwhitney"
        """
        scores_a = np.array(scores_a)
        scores_b = np.array(scores_b)

        if len(scores_a) < 3 or len(scores_b) < 3:
            raise ValueError("每组至少需要3个样本")

        # 基本统计
        mean_a, mean_b = np.mean(scores_a), np.mean(scores_b)
        std_a, std_b = np.std(scores_a, ddof=1), np.std(scores_b, ddof=1)

        # 选择检验方法
        if test_type == "auto":
            # Shapiro-Wilk正态性检验
            _, p_norm_a = stats.shapiro(scores_a) if len(scores_a) <= 5000 else (0.05, None)
            _, p_norm_b = stats.shapiro(scores_b) if len(scores_b) <= 5000 else (0.05, None)

            # 如果两组都正态且方差齐性，使用t检验；否则使用非参数检验
            if p_norm_a and p_norm_b and p_norm_a > 0.05 and p_norm_b > 0.05:
                _, p_levene = stats.levene(scores_a, scores_b)
                test_type = "ttest" if p_levene > 0.05 else "welch"
            else:
                test_type = "mannwhitney"

        # 执行检验
        if test_type == "ttest":
            t_stat, p_value = stats.ttest_ind(scores_a, scores_b)
        elif test_type == "welch":
            t_stat, p_value = stats.ttest_ind(scores_a, scores_b, equal_var=False)
        else:  # mannwhitney
            t_stat, p_value = stats.mannwhitneyu(scores_a, scores_b, alternative="two-sided")
            # Mann-Whitney U 转换为 z-score 用于效应量
            n1, n2 = len(scores_a), len(scores_b)
            U = t_stat
            z = (U - n1 * n2 / 2) / np.sqrt(n1 * n2 * (n1 + n2 + 1) / 12)
            t_stat = z

        # 计算效应量 (Cohen's d)
        pooled_std = np.sqrt(
            ((len(scores_a) - 1) * std_a**2 + (len(scores_b) - 1) * std_b**2)
            / (len(scores_a) + len(scores_b) - 2)
        )
        effect_size = (mean_b - mean_a) / pooled_std if pooled_std > 0 else 0

        # 效应量解释
        abs_effect = abs(effect_size)
        if abs_effect < 0.2:
            effect_interpretation = "negligible"
        elif abs_effect < 0.5:
            effect_interpretation = "small"
        elif abs_effect < 0.8:
            effect_interpretation = "medium"
        else:
            effect_interpretation = "large"

        # 计算置信区间 (使用 Welch's t 分布)
        n1, n2 = len(scores_a), len(scores_b)
        se = np.sqrt(std_a**2 / n1 + std_b**2 / n2)
        df = (std_a**2 / n1 + std_b**2 / n2) ** 2 / (
            (std_a**2 / n1) ** 2 / (n1 - 1) + (std_b**2 / n2) ** 2 / (n2 - 1)
        )
        t_crit = stats.t.ppf(1 - significance_level / 2, df)
        ci_lower = (mean_b - mean_a) - t_crit * se
        ci_upper = (mean_b - mean_a) + t_crit * se

        # 判断显著性
        is_significant = p_value < significance_level

        # 确定赢家
        if is_significant:
            if mean_b > mean_a:
                winner = "model_b"
                conclusion = (
                    f"Model B 显著优于 Model A (提升 {((mean_b - mean_a) / mean_a * 100):.1f}%)"
                )
            else:
                winner = "model_a"
                conclusion = (
                    f"Model A 显著优于 Model B (差距 {((mean_a - mean_b) / mean_b * 100):.1f}%)"
                )
        else:
            winner = "no_significant_difference"
            conclusion = "两模型无显著差异"

        return ABTestResult(
            model_a_name=model_a_name,
            model_b_name=model_b_name,
            n_samples=len(scores_a) + len(scores_b),
            mean_a=mean_a,
            mean_b=mean_b,
            std_a=std_a,
            std_b=std_b,
            t_statistic=t_stat,
            p_value=p_value,
            is_significant=is_significant,
            significance_level=significance_level,
            effect_size=effect_size,
            effect_interpretation=effect_interpretation,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            ci_confidence=1 - significance_level,
            winner=winner,
            conclusion=conclusion,
        )

    def calculate_confidence_interval(
        self, scores: list[float], confidence: float = 0.95, method: str = "t-distribution"
    ) -> ConfidenceInterval:
        """计算置信区间"""
        scores = np.array(scores)

        if len(scores) < 2:
            raise ValueError("至少需要2个样本")

        estimate = np.mean(scores)

        if method == "bootstrap":
            np.random.seed(self._random_seed)
            bootstrap_means = []
            for _ in range(self._bootstrap_iterations):
                sample = np.random.choice(scores, size=len(scores), replace=True)
                bootstrap_means.append(np.mean(sample))
            bootstrap_means = np.array(bootstrap_means)

            alpha = 1 - confidence
            lower_percentile = (alpha / 2) * 100
            upper_percentile = (1 - alpha / 2) * 100

            ci_lower = np.percentile(bootstrap_means, lower_percentile)
            ci_upper = np.percentile(bootstrap_means, upper_percentile)
            method_used = "bootstrap"
        else:
            std_err = stats.sem(scores)
            df = len(scores) - 1
            t_crit = stats.t.ppf((1 + confidence) / 2, df)

            ci_lower = estimate - t_crit * std_err
            ci_upper = estimate + t_crit * std_err
            method_used = "t-distribution"

        return ConfidenceInterval(
            estimate=estimate,
            lower=ci_lower,
            upper=ci_upper,
            confidence=confidence,
            method=method_used,
        )

    def compare_multiple_models(
        self,
        model_scores: dict[str, list[float]],
        baseline_model: str = None,
        significance_level: float = 0.05,
    ) -> dict[str, Any]:
        """多模型比较（与基线或两两比较）"""
        results = {}
        model_names = list(model_scores.keys())

        # 计算每模型的置信区间和基本统计
        for model_name, scores in model_scores.items():
            ci = self.calculate_confidence_interval(scores)
            results[model_name] = {
                "mean": round(np.mean(scores), 4),
                "std": round(np.std(scores, ddof=1), 4),
                "n": len(scores),
                "ci": ci.to_dict(),
            }

        # 如果有基线模型，进行与基线的比较
        if baseline_model and baseline_model in model_scores:
            for model_name in model_names:
                if model_name != baseline_model:
                    result = self.run_ab_test(
                        scores_a=model_scores[baseline_model],
                        scores_b=model_scores[model_name],
                        model_a_name=baseline_model,
                        model_b_name=model_name,
                        significance_level=significance_level,
                    )
                    results[model_name]["ab_test"] = result.to_dict()

        return {
            "models": results,
            "significance_level": significance_level,
            "best_model": (
                max(model_names, key=lambda x: np.mean(model_scores[x])) if model_scores else None
            ),
            "timestamp": datetime.utcnow().isoformat(),
        }

    def power_analysis(
        self, effect_size: float = 0.5, significance_level: float = 0.05, power: float = 0.8
    ) -> dict[str, Any]:
        """统计功效分析 - 计算所需样本量"""
        from scipy.stats import norm

        z_alpha = norm.ppf(1 - significance_level / 2)
        z_beta = norm.ppf(power)

        # 所需样本量 (每组)
        n = 2 * ((z_alpha + z_beta) / effect_size) ** 2

        return {
            "required_samples_per_group": int(np.ceil(n)),
            "total_samples_needed": int(np.ceil(n * 2)),
            "effect_size": effect_size,
            "significance_level": significance_level,
            "power": power,
        }


# 全局实例
statistical_analyzer = StatisticalSignificanceAnalyzer()
