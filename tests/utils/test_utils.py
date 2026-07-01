"""utils工具测试"""

import pytest
from tests.utils.assertion_analyzer import analyze_file, generate_report, AssertionPatterns
from tests.utils.confidence_analyzer import analyze_confidence, generate_report as gen_conf_report


class TestAssertionAnalyzer:
    """断言强度分析工具测试"""

    def test_analyze_file_with_strong_assertions(self, tmp_path):
        """分析包含强断言的文件"""
        test_file = tmp_path / "test_example.py"
        test_file.write_text("""
def test_example():
    assert result.score == pytest.approx(0.85, abs=0.01)
    assert mock_client.chat.assert_called_with("expected prompt")
""")

        stats = analyze_file(str(test_file))

        assert stats.strong_count >= 1
        assert stats.strong_ratio > 0.5

    def test_analyze_file_with_only_weak_assertions(self, tmp_path):
        """分析只包含弱断言的文件"""
        test_file = tmp_path / "test_bad.py"
        test_file.write_text("""
def test_bad():
    assert result.is_valid is True
    assert result.score is not None
    mock_client.chat.assert_called_once()
""")

        stats = analyze_file(str(test_file))

        assert stats.strong_count == 0
        assert stats.strong_ratio == 0.0

    def test_analyze_file_empty(self, tmp_path):
        """分析空文件"""
        test_file = tmp_path / "test_empty.py"
        test_file.write_text("")

        stats = analyze_file(str(test_file))

        assert stats.total_assertions == 0
        assert stats.strong_ratio == 0.0

    def test_generate_report_passes(self):
        """生成通过的报告"""
        stats_list = [
            type('obj', (object,), {'strong_ratio': 0.6, 'file_path': 'test1.py', 'total_assertions': 5}),
            type('obj', (object,), {'strong_ratio': 0.8, 'file_path': 'test2.py', 'total_assertions': 6}),
        ]

        report = generate_report(stats_list)

        assert report['all_passed'] is True

    def test_generate_report_fails(self):
        """生成失败的报告"""
        stats_list = [
            type('obj', (object,), {'strong_ratio': 0.6, 'file_path': 'test1.py', 'total_assertions': 5}),
            type('obj', (object,), {'strong_ratio': 0.3, 'file_path': 'test2.py', 'total_assertions': 4}),
        ]

        report = generate_report(stats_list)

        assert report['all_passed'] is False


class TestConfidenceAnalyzer:
    """统计置信度分析工具测试"""

    def test_analyze_confidence_with_consistent_scores(self):
        """分析一致性好的评分"""
        scores = [0.85, 0.87, 0.83, 0.86, 0.84, 0.88, 0.85, 0.86, 0.87, 0.84]
        result = analyze_confidence(scores)

        assert result['std_dev'] < 0.05
        assert result['cv'] < 0.1

    def test_analyze_confidence_small_sample(self):
        """分析小样本评分（跳过正态性检验）"""
        scores = [0.85, 0.87, 0.83]
        result = analyze_confidence(scores)

        assert result['normality_p_value'] is None
        assert result['is_normal'] is None

    def test_generate_report_passes(self):
        """生成通过的报告"""
        scores = [0.85, 0.87, 0.83, 0.86, 0.84]
        report = gen_conf_report(scores)

        assert report['all_passed'] is True

    def test_generate_report_fails(self):
        """生成失败的报告"""
        scores = [0.6, 0.5, 0.4, 0.3, 0.2]
        report = gen_conf_report(scores)

        assert report['all_passed'] is False

    def test_generate_report_low_consistency(self):
        """生成一致性差的报告"""
        scores = [0.9, 0.1, 0.8, 0.2, 0.7]
        report = gen_conf_report(scores)

        assert report['all_passed'] is False