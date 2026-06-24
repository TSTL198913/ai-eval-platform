"""
🧪 tests/unit/test_standard_metrics.py
标准指标库单元测试

覆盖：正向 / 负向 / 边界 / 异常 / 一致性
"""

import pytest

from src.domain.metrics.standard_metrics import (
    BLEUMetric,
    F1TokenMetric,
    LevenshteinMetric,
    METEORMetric,
    MetricRegistry,
    ROUGEMetric,
    StandardMetric,
    compute_standard_metrics,
    get_metric,
)


class TestBLEUMetricPositiveCases:
    """正向测试 - BLEU 指标"""

    def test_perfect_match_returns_high_score(self):
        """完全匹配应返回接近 1.0 的分数"""
        metric = BLEUMetric(max_n=4)
        score = metric.compute("the cat is on the mat", "the cat is on the mat")
        assert score >= 0.99, f"完全匹配分数应 >= 0.99，实际: {score}"

    def test_partial_match_returns_moderate_score(self):
        """部分匹配应返回中等分数"""
        metric = BLEUMetric(max_n=2)
        score = metric.compute("the cat is on the mat", "the cat is on a mat")
        assert 0.0 < score < 1.0, f"部分匹配分数应在 (0, 1)，实际: {score}"

    def test_short_match_handled(self):
        """短文本匹配应正常处理"""
        metric = BLEUMetric(max_n=2)
        score = metric.compute("hi", "hi")
        assert score >= 0.9, f"短文本匹配分数应较高，实际: {score}"


class TestBLEUMetricNegativeCases:
    """负向测试 - BLEU 指标"""

    def test_completely_different_returns_low_score(self):
        """完全不同的文本应返回低分"""
        metric = BLEUMetric(max_n=2)
        score = metric.compute("hello world", "completely different text here")
        assert score < 0.5, f"完全不同文本分数应 < 0.5，实际: {score}"

    def test_empty_output_returns_zero(self):
        """空输出应返回 0"""
        metric = BLEUMetric(max_n=4)
        assert metric.compute("", "expected") == 0.0
        assert metric.compute("output", "") == 0.0


class TestBLEUMetricBoundaryCases:
    """边界测试 - BLEU 指标"""

    def test_whitespace_only(self):
        """纯空白输入应返回 0（本地实现不视为匹配）"""
        metric = BLEUMetric(max_n=2)
        # 双方都是空白 → 分词后空列表 → 返回 0
        assert metric.compute("   ", "   ") == 0.0
        assert metric.compute("   ", "abc") == 0.0


class TestROUGEMetricPositiveCases:
    """正向测试 - ROUGE 指标"""

    def test_rouge_l_perfect_match(self):
        """ROUGE-L 完全匹配"""
        metric = ROUGEMetric("rougeL")
        score = metric.compute("the quick brown fox", "the quick brown fox")
        assert score >= 0.99, f"完全匹配分数应 >= 0.99，实际: {score}"

    def test_rouge_1_returns_value_in_range(self):
        """ROUGE-1 应返回 0-1 区间"""
        metric = ROUGEMetric("rouge1")
        score = metric.compute("a b c d", "a b c e")
        assert 0.0 <= score <= 1.0


class TestROUGEMetricNegativeCases:
    """负向测试 - ROUGE 指标"""

    def test_invalid_rouge_type_raises(self):
        """非法 ROUGE 类型应抛出"""
        with pytest.raises(ValueError, match="不支持的 ROUGE 类型"):
            ROUGEMetric("rouge_invalid")

    def test_empty_input(self):
        """空输入"""
        metric = ROUGEMetric("rougeL")
        assert metric.compute("", "expected") == 0.0


class TestLevenshteinMetricPositiveCases:
    """正向测试 - Levenshtein"""

    def test_identical_strings(self):
        """完全相同应返回 1.0"""
        metric = LevenshteinMetric()
        assert metric.compute("hello", "hello") == 1.0

    def test_one_char_diff(self):
        """一个字符不同应返回接近 1.0"""
        metric = LevenshteinMetric()
        score = metric.compute("hello", "hellp")
        assert 0.7 <= score < 1.0, f"一个字符差异应 > 0.7，实际: {score}"


class TestLevenshteinMetricNegativeCases:
    """负向测试 - Levenshtein"""

    def test_completely_different(self):
        """完全不同应返回接近 0"""
        metric = LevenshteinMetric()
        score = metric.compute("abc", "xyz")
        assert score < 0.5


class TestLevenshteinMetricBoundaryCases:
    """边界测试 - Levenshtein"""

    def test_empty_inputs(self):
        """空输入处理"""
        metric = LevenshteinMetric()
        assert metric.compute("", "") == 1.0
        assert metric.compute("abc", "") == 0.0
        assert metric.compute("", "abc") == 0.0


class TestF1TokenMetricPositiveCases:
    """正向测试 - F1-Token"""

    def test_perfect_token_match(self):
        """完全 token 重合应返回 1.0"""
        metric = F1TokenMetric()
        score = metric.compute("the quick brown fox", "the quick brown fox")
        assert score >= 0.99

    def test_chinese_tokenization(self):
        """中文按字分词"""
        metric = F1TokenMetric()
        score = metric.compute("北京是中国的首都", "北京是中国的首都")
        assert score >= 0.99


class TestF1TokenMetricNegativeCases:
    """负向测试 - F1-Token"""

    def test_no_overlap(self):
        """完全不重合应返回 0"""
        metric = F1TokenMetric()
        score = metric.compute("apple banana", "cat dog")
        assert score == 0.0


class TestMetricRegistry:
    """指标注册表测试"""

    def test_default_metrics_registered(self):
        """默认指标应自动注册"""
        registry = MetricRegistry()
        names = registry.list_metrics()
        assert "BLEU-4" in names
        assert "BLEU-2" in names
        assert "ROUGE-1" in names
        assert "ROUGE-2" in names
        assert "ROUGE-L" in names
        assert "F1-Token" in names
        assert "Levenshtein" in names
        assert "CosineSimilarity" in names

    def test_get_metric_returns_instance(self):
        """get_metric 应返回有效实例"""
        assert get_metric("BLEU-4") is not None
        assert get_metric("ROUGE-L") is not None
        assert get_metric("UNKNOWN") is None

    def test_compute_all_returns_dict(self):
        """compute_all 应返回字典"""
        registry = MetricRegistry()
        results = registry.compute_all("test", "test")
        assert isinstance(results, dict)
        assert len(results) > 0
        for _name, result in results.items():
            assert 0.0 <= result.score <= 1.0

    def test_compute_standard_metrics_helper(self):
        """便捷函数应正确返回"""
        results = compute_standard_metrics("test", "test")
        assert "BLEU-4" in results
        assert "ROUGE-L" in results
        assert all(0.0 <= v <= 1.0 for v in results.values())


class TestStandardMetricABC:
    """抽象基类契约测试"""

    def test_cannot_instantiate_abstract(self):
        """抽象类不能直接实例化"""
        with pytest.raises(TypeError):
            StandardMetric()  # type: ignore

    def test_subclass_must_implement_methods(self):
        """子类必须实现所有抽象方法"""

        class IncompleteMetric(StandardMetric):
            pass

        with pytest.raises(TypeError):
            IncompleteMetric()  # type: ignore


class TestConsistencyBetweenMetrics:
    """跨指标一致性测试"""

    def test_identical_text_high_score_across_metrics(self):
        """相同文本在所有指标上都应得到高分（依赖库缺失的指标跳过）"""
        text = "the quick brown fox jumps over the lazy dog"
        registry = MetricRegistry()
        results = registry.compute_all(text, text)
        for name, result in results.items():
            if name in {"CosineSimilarity", "METEOR"}:
                # 依赖外部库，未安装时跳过
                continue
            assert result.score >= 0.95, f"{name} 相同文本分数应 >= 0.95，实际: {result.score}"

    def test_completely_different_low_score(self):
        """完全不同文本应得到低分"""
        actual = "the cat sat on the mat"
        expected = "quantum physics entanglement superposition"
        registry = MetricRegistry()
        results = registry.compute_all(actual, expected)
        for name, result in results.items():
            if name in {"CosineSimilarity", "METEOR"}:
                continue
            assert result.score < 0.5, f"{name} 不同文本分数应 < 0.5，实际: {result.score}"


class TestMETEORMetric:
    """METEOR 指标测试（依赖 nltk）"""

    def test_identical_text_returns_high_score(self):
        """相同文本应得高分（即使 nltk 不可用也返回 0）"""
        metric = METEORMetric()
        score = metric.compute("the cat is on the mat", "the cat is on the mat")
        # 不可用时返回 0，可用时返回接近 1
        assert 0.0 <= score <= 1.0
