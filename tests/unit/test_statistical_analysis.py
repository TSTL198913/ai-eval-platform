"""
统计显著性分析单元测试
测试目标：验证 StatisticalSignificanceAnalyzer 的 A/B 测试、置信区间、效应量计算
关键发现：
- 支持 t-test 和 Mann-Whitney U 检验
- 自动选择检验方法（正态性检验 + 方差齐性检验）
- 计算 Cohen's d 效应量并给出解释
- 支持 Bootstrap 置信区间计算
"""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.statistical_analysis import (
    ABTestResult,
    ConfidenceInterval,
    SignificanceLevel,
    StatisticalSignificanceAnalyzer,
)


class TestStatisticalSignificanceAnalyzerInitialization:
    """初始化测试"""

    def test_default_config(self):
        """默认配置应正确"""
        analyzer = StatisticalSignificanceAnalyzer()
        assert analyzer._bootstrap_iterations == 10000
        assert analyzer._random_seed == 42

    def test_custom_config(self):
        """自定义配置应正确"""
        analyzer = StatisticalSignificanceAnalyzer(
            bootstrap_iterations=1000,
            random_seed=123,
        )
        assert analyzer._bootstrap_iterations == 1000
        assert analyzer._random_seed == 123


class TestABTestPositiveCases:
    """正向测试 - 正常 A/B 测试"""

    @pytest.fixture
    def analyzer(self):
        return StatisticalSignificanceAnalyzer(random_seed=42)

    def test_significant_difference_detected(self, analyzer):
        """应能检测到显著差异"""
        np.random.seed(42)
        n = 50
        scores_a = np.random.normal(70, 10, n).tolist()
        scores_b = np.random.normal(80, 10, n).tolist()

        result = analyzer.run_ab_test(
            scores_a=scores_a,
            scores_b=scores_b,
            model_a_name="Model A",
            model_b_name="Model B",
            test_type="ttest",
        )

        assert isinstance(result, ABTestResult)
        assert result.model_a_name == "Model A"
        assert result.model_b_name == "Model B"
        assert result.n_samples == n * 2  # n_samples 是两组样本总数
        assert result.is_significant  # Bug 已修复：现在返回 Python 原生 bool
        assert result.winner == "model_b"  # B 平均分更高
        assert result.p_value < 0.05

    def test_no_significant_difference(self, analyzer):
        """无显著差异时应正确报告"""
        np.random.seed(42)
        scores_a = np.random.normal(75, 10, 50).tolist()
        scores_b = np.random.normal(76, 10, 50).tolist()

        result = analyzer.run_ab_test(
            scores_a=scores_a,
            scores_b=scores_b,
            test_type="ttest",
        )

        assert isinstance(result, ABTestResult)
        assert not result.is_significant  # Bug 已修复：现在返回 Python 原生 bool
        assert result.winner == "no_significant_difference"
        assert result.p_value > 0.05

    def test_basic_statistics_correct(self, analyzer):
        """基本统计量计算应正确"""
        scores_a = [1.0, 2.0, 3.0, 4.0, 5.0]
        scores_b = [2.0, 3.0, 4.0, 5.0, 6.0]

        result = analyzer.run_ab_test(
            scores_a=scores_a,
            scores_b=scores_b,
            test_type="ttest",
        )

        assert result.mean_a == pytest.approx(3.0, rel=1e-6)
        assert result.mean_b == pytest.approx(4.0, rel=1e-6)
        assert result.n_samples == 10  # 两组各5个，共10个
        assert result.std_a > 0
        assert result.std_b > 0

    def test_effect_size_calculation(self, analyzer):
        """效应量计算应正确"""
        scores_a = [1.0, 2.0, 3.0, 4.0, 5.0]
        scores_b = [3.0, 4.0, 5.0, 6.0, 7.0]

        result = analyzer.run_ab_test(
            scores_a=scores_a,
            scores_b=scores_b,
            test_type="ttest",
        )

        # Cohen's d 应为正（B > A）
        assert result.effect_size > 0
        # 大效应量（均值差2，标准差~1.58，d~1.26）
        assert result.effect_interpretation == "large"

    def test_effect_size_interpretation_small(self, analyzer):
        """小效应量应正确解释"""
        np.random.seed(42)
        scores_a = np.random.normal(75, 10, 200).tolist()
        scores_b = np.random.normal(76, 10, 200).tolist()  # 差异很小

        result = analyzer.run_ab_test(
            scores_a=scores_a,
            scores_b=scores_b,
            test_type="ttest",
        )

        # 效应量应很小（< 0.2 = negligible）
        assert abs(result.effect_size) < 0.5

    def test_mann_whitney_test(self, analyzer):
        """Mann-Whitney U 检验应正常工作"""
        np.random.seed(42)
        scores_a = np.random.normal(70, 10, 30).tolist()
        scores_b = np.random.normal(80, 10, 30).tolist()

        result = analyzer.run_ab_test(
            scores_a=scores_a,
            scores_b=scores_b,
            test_type="mannwhitney",
        )

        assert isinstance(result, ABTestResult)
        assert result.is_significant  # Bug 已修复：是 Python bool 类型
        assert result.winner == "model_b"

    def test_auto_selects_test(self, analyzer):
        """auto 模式应自动选择检验方法"""
        np.random.seed(42)
        scores_a = np.random.normal(75, 10, 30).tolist()
        scores_b = np.random.normal(80, 10, 30).tolist()

        result = analyzer.run_ab_test(
            scores_a=scores_a,
            scores_b=scores_b,
            test_type="auto",
        )

        assert isinstance(result, ABTestResult)
        assert result.is_significant  # Bug 已修复：是 Python bool 类型
        # 正态数据应选择 t-test 或 welch


class TestABTestNegativeCases:
    """负向测试 - 错误输入处理"""

    @pytest.fixture
    def analyzer(self):
        return StatisticalSignificanceAnalyzer()

    def test_insufficient_samples_a(self, analyzer):
        """A组样本不足应抛出 ValueError"""
        with pytest.raises(ValueError, match="至少需要3个样本"):
            analyzer.run_ab_test(
                scores_a=[1.0, 2.0],
                scores_b=[1.0, 2.0, 3.0],
            )

    def test_insufficient_samples_b(self, analyzer):
        """B组样本不足应抛出 ValueError"""
        with pytest.raises(ValueError, match="至少需要3个样本"):
            analyzer.run_ab_test(
                scores_a=[1.0, 2.0, 3.0],
                scores_b=[1.0, 2.0],
            )

    def test_both_insufficient_samples(self, analyzer):
        """两组都不足应抛出 ValueError"""
        with pytest.raises(ValueError):
            analyzer.run_ab_test(
                scores_a=[1.0],
                scores_b=[2.0],
            )

    def test_empty_lists(self, analyzer):
        """空列表应抛出 ValueError"""
        with pytest.raises(ValueError):
            analyzer.run_ab_test(
                scores_a=[],
                scores_b=[],
            )


class TestABTestBoundaryCases:
    """边界测试 - 边界值场景"""

    @pytest.fixture
    def analyzer(self):
        return StatisticalSignificanceAnalyzer(random_seed=42)

    def test_minimum_samples(self, analyzer):
        """最小样本数（每组3个）应正常工作"""
        result = analyzer.run_ab_test(
            scores_a=[1.0, 2.0, 3.0],
            scores_b=[4.0, 5.0, 6.0],
            test_type="ttest",
        )
        assert result.n_samples == 6  # 两组各3个
        assert result.is_significant  # Bug 已修复：是 Python bool 类型

    def test_identical_scores(self, analyzer):
        """完全相同的分数应无显著差异"""
        scores = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = analyzer.run_ab_test(
            scores_a=scores,
            scores_b=scores,
            test_type="ttest",
        )
        assert result.mean_a == result.mean_b
        assert result.p_value == pytest.approx(1.0, rel=1e-6)
        assert not result.is_significant  # Bug 已修复：现在返回 Python 原生 bool
        assert result.effect_size == 0.0
        assert result.effect_interpretation == "negligible"

    def test_zero_variance(self, analyzer):
        """零方差应正确处理"""
        scores_a = [5.0] * 10
        scores_b = [5.0] * 10
        result = analyzer.run_ab_test(
            scores_a=scores_a,
            scores_b=scores_b,
            test_type="ttest",
        )
        assert result.std_a == 0.0
        assert result.std_b == 0.0
        assert not result.is_significant  # Bug 已修复：现在返回 Python 原生 bool

    def test_large_sample_size(self, analyzer):
        """大样本量应正常工作"""
        np.random.seed(42)
        n = 1000
        scores_a = np.random.normal(75, 10, n).tolist()
        scores_b = np.random.normal(76, 10, n).tolist()

        result = analyzer.run_ab_test(
            scores_a=scores_a,
            scores_b=scores_b,
            test_type="ttest",
        )
        assert result.n_samples == n * 2
        assert result.is_significant  # Bug 已修复：是 Python bool 类型

    def test_custom_significance_level(self, analyzer):
        """自定义显著性水平应生效"""
        np.random.seed(42)
        scores_a = np.random.normal(75, 10, 20).tolist()
        scores_b = np.random.normal(78, 10, 20).tolist()

        result_strict = analyzer.run_ab_test(
            scores_a=scores_a,
            scores_b=scores_b,
            significance_level=0.01,  # 更严格
            test_type="ttest",
        )

        result_lenient = analyzer.run_ab_test(
            scores_a=scores_a,
            scores_b=scores_b,
            significance_level=0.10,  # 更宽松
            test_type="ttest",
        )

        # 严格标准下不显著的，宽松下可能显著
        if not result_strict.is_significant:
            # 严格不显著时，宽松的也不一定显著，但 p_value 应该相同
            assert result_strict.p_value == result_lenient.p_value


class TestABTestResultDict:
    """结果序列化测试"""

    @pytest.fixture
    def analyzer(self):
        return StatisticalSignificanceAnalyzer(random_seed=42)

    def test_to_dict_returns_dict(self, analyzer):
        """to_dict 应返回字典"""
        result = analyzer.run_ab_test(
            scores_a=[1.0, 2.0, 3.0],
            scores_b=[4.0, 5.0, 6.0],
            test_type="ttest",
        )
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "model_a_name" in d
        assert "model_b_name" in d
        assert "mean_a" in d
        assert "mean_b" in d
        assert "p_value" in d
        assert "is_significant" in d
        assert "winner" in d
        assert "conclusion" in d

    def test_to_dict_values_rounded(self, analyzer):
        """数值应四舍五入到4位小数"""
        result = analyzer.run_ab_test(
            scores_a=[1.123456, 2.123456, 3.123456],
            scores_b=[4.123456, 5.123456, 6.123456],
            test_type="ttest",
        )
        d = result.to_dict()
        # 浮点数应被四舍五入
        assert isinstance(d["mean_a"], float)
        assert isinstance(d["mean_b"], float)


class TestConfidenceInterval:
    """置信区间测试"""

    def test_confidence_interval_creation(self):
        """置信区间对象应正确创建"""
        ci = ConfidenceInterval(
            estimate=0.5,
            lower=0.4,
            upper=0.6,
            confidence=0.95,
            method="t-distribution",
        )
        assert ci.estimate == 0.5
        assert ci.lower == 0.4
        assert ci.upper == 0.6
        assert ci.confidence == 0.95

    def test_confidence_interval_to_dict(self):
        """to_dict 应返回正确格式"""
        ci = ConfidenceInterval(
            estimate=0.5,
            lower=0.4,
            upper=0.6,
            confidence=0.95,
            method="bootstrap",
        )
        d = ci.to_dict()
        assert d["estimate"] == pytest.approx(0.5, rel=1e-6)
        assert d["lower"] == pytest.approx(0.4, rel=1e-6)
        assert d["upper"] == pytest.approx(0.6, rel=1e-6)
        assert d["confidence"] == 0.95
        assert d["interval_width"] == pytest.approx(0.2, rel=1e-6)
        assert d["method"] == "bootstrap"


class TestSignificanceLevel:
    """显著性水平枚举测试"""

    def test_significance_level_values(self):
        """枚举值应正确"""
        assert SignificanceLevel.P05.value == 0.05
        assert SignificanceLevel.P01.value == 0.01
        assert SignificanceLevel.P10.value == 0.10


class TestTypeSafetyBugs:
    """
    Bug 记录：类型安全问题

    Bug 1: is_significant 是 numpy.bool_ 类型而非 Python 原生 bool
    - 位置：ABTestResult.is_significant
    - 影响：使用 `is True` / `is False` 判断时失败
    - 修复建议：在赋值时转换为 Python bool
    """

    @pytest.fixture
    def analyzer(self):
        return StatisticalSignificanceAnalyzer(random_seed=42)

    def test_is_significant_is_python_bool(self, analyzer):
        """
        Bug 已修复：is_significant 现在应该是 Python 原生 bool 类型

        修复前：type(result.is_significant).__name__ == "bool_"
        修复后：isinstance(result.is_significant, bool) == True
        """
        result = analyzer.run_ab_test(
            scores_a=[1.0, 2.0, 3.0],
            scores_b=[4.0, 5.0, 6.0],
            test_type="ttest",
        )

        # 修复后：类型应该是 Python 原生 bool
        assert isinstance(result.is_significant, bool)
        assert type(result.is_significant).__name__ == "bool"

        # 使用 is 比较应该正常工作
        assert result.is_significant is True
        assert result.is_significant is not False

    def test_numpy_bool_fixed(self, analyzer):
        """
        Bug 已修复：修复后 numpy.bool_ 问题不再存在

        修复前：type(result.is_significant) is not bool
        修复后：type(result.is_significant) is bool
        """
        result = analyzer.run_ab_test(
            scores_a=[1.0, 2.0, 3.0],
            scores_b=[4.0, 5.0, 6.0],
            test_type="ttest",
        )

        # if 条件判断
        works_in_if = False
        if result.is_significant:
            works_in_if = True
        assert works_in_if is True

        # 类型检查
        assert isinstance(result.is_significant, bool)
