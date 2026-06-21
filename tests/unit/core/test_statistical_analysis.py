"""
统计显著性分析模块测试
"""

import numpy as np
import pytest

from src.domain.statistical_analysis import (
    ABTestResult,
    ConfidenceInterval,
    StatisticalSignificanceAnalyzer,
)


class TestStatisticalSignificanceAnalyzer:
    """统计显著性分析器测试"""

    def setup_method(self):
        """测试前准备"""
        self.analyzer = StatisticalSignificanceAnalyzer(bootstrap_iterations=1000, random_seed=42)

    def test_ab_test_ttest_significant_difference(self):
        """测试t检验 - 显著差异"""
        scores_a = [0.7, 0.75, 0.72, 0.68, 0.71]
        scores_b = [0.85, 0.88, 0.82, 0.87, 0.86]

        result = self.analyzer.run_ab_test(
            scores_a=scores_a,
            scores_b=scores_b,
            model_a_name="Model A",
            model_b_name="Model B",
            significance_level=0.05,
            test_type="ttest",
        )

        assert isinstance(result, ABTestResult)
        assert result.mean_a < result.mean_b
        assert result.is_significant
        assert result.winner == "model_b"
        assert result.p_value < 0.05

    def test_ab_test_no_significant_difference(self):
        """测试t检验 - 无显著差异"""
        scores_a = [0.8, 0.82, 0.81, 0.79, 0.80]
        scores_b = [0.81, 0.79, 0.80, 0.82, 0.80]

        result = self.analyzer.run_ab_test(
            scores_a=scores_a, scores_b=scores_b, significance_level=0.05, test_type="ttest"
        )

        assert not result.is_significant
        assert result.winner == "no_significant_difference"

    def test_ab_test_mannwhitney(self):
        """测试Mann-Whitney U检验"""
        scores_a = [0.7, 0.75, 0.72, 0.68, 0.71]
        scores_b = [0.85, 0.88, 0.82, 0.87, 0.86]

        result = self.analyzer.run_ab_test(
            scores_a=scores_a, scores_b=scores_b, test_type="mannwhitney"
        )

        assert isinstance(result, ABTestResult)
        assert result.is_significant

    def test_ab_test_auto_selection(self):
        """测试自动选择检验方法"""
        scores_a = [0.7, 0.75, 0.72, 0.68, 0.71]
        scores_b = [0.85, 0.88, 0.82, 0.87, 0.86]

        result = self.analyzer.run_ab_test(scores_a=scores_a, scores_b=scores_b, test_type="auto")

        # 自动选择应选择合适的检验方法
        assert result.p_value is not None

    def test_ab_test_small_sample(self):
        """测试小样本"""
        scores_a = [0.75, 0.80, 0.78]
        scores_b = [0.85, 0.88, 0.82]

        result = self.analyzer.run_ab_test(scores_a=scores_a, scores_b=scores_b)

        assert result.n_samples == 6

    def test_ab_test_invalid_sample_size(self):
        """测试样本不足"""
        scores_a = [0.7, 0.75]
        scores_b = [0.85, 0.88]

        with pytest.raises(ValueError, match="至少需要3个样本"):
            self.analyzer.run_ab_test(scores_a=scores_a, scores_b=scores_b)

    def test_confidence_interval_t_distribution(self):
        """测试t分布置信区间"""
        scores = [0.75, 0.80, 0.78, 0.82, 0.77, 0.81, 0.79, 0.76, 0.83, 0.80]

        ci = self.analyzer.calculate_confidence_interval(
            scores=scores, confidence=0.95, method="t-distribution"
        )

        assert isinstance(ci, ConfidenceInterval)
        assert ci.confidence == 0.95
        assert ci.lower < ci.estimate < ci.upper
        assert ci.method == "t-distribution"

    def test_confidence_interval_bootstrap(self):
        """测试Bootstrap置信区间"""
        scores = [0.75, 0.80, 0.78, 0.82, 0.77, 0.81, 0.79, 0.76, 0.83, 0.80]

        ci = self.analyzer.calculate_confidence_interval(
            scores=scores, confidence=0.95, method="bootstrap"
        )

        assert isinstance(ci, ConfidenceInterval)
        assert ci.confidence == 0.95
        assert ci.lower < ci.estimate < ci.upper
        assert ci.method == "bootstrap"

    def test_confidence_interval_invalid_sample(self):
        """测试无效样本"""
        with pytest.raises(ValueError, match="至少需要2个样本"):
            self.analyzer.calculate_confidence_interval(scores=[0.8])

    def test_compare_multiple_models(self):
        """测试多模型比较"""
        model_scores = {
            "Model A": [0.70, 0.72, 0.68, 0.71, 0.73],
            "Model B": [0.85, 0.88, 0.82, 0.87, 0.86],
            "Model C": [0.75, 0.77, 0.74, 0.76, 0.78],
        }

        result = self.analyzer.compare_multiple_models(
            model_scores=model_scores, baseline_model="Model A", significance_level=0.05
        )

        assert "models" in result
        assert "Model A" in result["models"]
        assert "Model B" in result["models"]
        assert result["best_model"] == "Model B"

    def test_power_analysis(self):
        """测试统计功效分析"""
        result = self.analyzer.power_analysis(effect_size=0.5, significance_level=0.05, power=0.8)

        assert "required_samples_per_group" in result
        assert "total_samples_needed" in result
        assert result["effect_size"] == 0.5
        assert result["power"] == 0.8

    def test_effect_size_interpretation(self):
        """测试效应量解释"""
        scores_a = [0.7, 0.72, 0.68, 0.71, 0.73]
        scores_b = [0.72, 0.74, 0.70, 0.73, 0.75]

        result = self.analyzer.run_ab_test(scores_a, scores_b)

        # 小效应量
        assert result.effect_interpretation in ["negligible", "small", "medium", "large"]

    def test_ab_test_result_to_dict(self):
        """测试结果序列化"""
        scores_a = [0.7, 0.75, 0.72]
        scores_b = [0.85, 0.88, 0.82]

        result = self.analyzer.run_ab_test(scores_a, scores_b)
        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert "model_a_name" in result_dict
        assert "model_b_name" in result_dict
        assert "p_value" in result_dict
        assert "is_significant" in result_dict
        assert "timestamp" in result_dict

    def test_confidence_interval_to_dict(self):
        """测试置信区间序列化"""
        scores = [0.75, 0.80, 0.78, 0.82, 0.77]

        ci = self.analyzer.calculate_confidence_interval(scores=scores)
        ci_dict = ci.to_dict()

        assert isinstance(ci_dict, dict)
        assert "estimate" in ci_dict
        assert "lower" in ci_dict
        assert "upper" in ci_dict
        assert "interval_width" in ci_dict

    def test_ab_test_large_sample(self):
        """测试大样本"""
        np.random.seed(42)
        scores_a = np.random.normal(0.75, 0.05, 100).tolist()
        scores_b = np.random.normal(0.80, 0.05, 100).tolist()

        result = self.analyzer.run_ab_test(scores_a, scores_b)
        assert result.n_samples == 200

    def test_ab_test_with_different_variances(self):
        """测试方差不等情况"""
        scores_a = [0.7, 0.75, 0.72, 0.68, 0.71]  # 低方差
        scores_b = [0.85, 0.92, 0.70, 0.95, 0.75]  # 高方差

        result = self.analyzer.run_ab_test(scores_a=scores_a, scores_b=scores_b, test_type="welch")

        assert result.std_a < result.std_b
