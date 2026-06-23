"""
🧪 tests/unit/test_report_generator.py
报告生成器单元测试
"""
import json
import tempfile
from pathlib import Path

import pytest

from src.infra.analytics.report_generator import ReportGenerator
from src.infra.analytics.visualization_service import VisualizationService


@pytest.fixture
def sample_evaluations():
    return [
        {
            "evaluator_type": "ragas",
            "score": 0.9,
            "status": "success",
            "latency_ms": 120,
            "created_at": "2024-01-01T00:00:00",
        },
        {
            "evaluator_type": "deepeval",
            "score": 0.85,
            "status": "success",
            "latency_ms": 200,
            "created_at": "2024-01-02T00:00:00",
        },
    ]


class TestHTMLReportPositiveCases:
    """正向测试 - HTML 报告"""

    def test_html_report_generated(self, sample_evaluations):
        """HTML 报告生成"""
        gen = ReportGenerator(title="测试报告")
        html = gen.generate_html_report(sample_evaluations)
        assert "<!DOCTYPE html>" in html
        assert "测试报告" in html
        assert "echarts" in html.lower()

    def test_html_report_contains_charts(self, sample_evaluations):
        """报告应包含各类图表"""
        gen = ReportGenerator()
        html = gen.generate_html_report(sample_evaluations)
        assert "radar-chart" in html
        assert "trend-chart" in html
        assert "distribution-chart" in html
        assert "boxplot-chart" in html
        assert "heatmap-chart" in html

    def test_html_report_contains_kpis(self, sample_evaluations):
        """报告应包含 KPI"""
        gen = ReportGenerator()
        html = gen.generate_html_report(sample_evaluations)
        assert "kpi-row" in html
        assert "总评估数" in html

    def test_write_html_to_file(self, sample_evaluations):
        """写入文件"""
        gen = ReportGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.html"
            written = gen.write_html_report(sample_evaluations, path)
            assert written.exists()
            assert written.stat().st_size > 0


class TestHTMLReportNegativeCases:
    """负向测试 - HTML 报告"""

    def test_empty_evaluations_generates_valid_html(self):
        """空评估列表仍生成有效 HTML"""
        gen = ReportGenerator()
        html = gen.generate_html_report([])
        assert "<!DOCTYPE html>" in html
        assert "总评估数: 0" in html


class TestJSONReportPositiveCases:
    """正向测试 - JSON 报告"""

    def test_json_data_structure(self, sample_evaluations):
        """JSON 数据结构"""
        gen = ReportGenerator()
        data = gen.generate_json_data(sample_evaluations)
        assert "title" in data
        assert "generated_at" in data
        assert "dashboard" in data
        assert "evaluations" in data
        assert len(data["evaluations"]) == 2

    def test_write_json_to_file(self, sample_evaluations):
        """JSON 写入文件"""
        gen = ReportGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.json"
            written = gen.write_json_report(sample_evaluations, path)
            assert written.exists()
            content = json.loads(written.read_text(encoding="utf-8"))
            assert content["title"]


class TestMarkdownReportPositiveCases:
    """正向测试 - Markdown 报告"""

    def test_markdown_contains_kpi(self, sample_evaluations):
        """Markdown 包含 KPI"""
        gen = ReportGenerator()
        md = gen.generate_markdown_report(sample_evaluations)
        assert "# " in md
        assert "KPI 概览" in md
        assert "总评估数" in md

    def test_markdown_contains_distribution(self, sample_evaluations):
        """Markdown 包含分布统计"""
        gen = ReportGenerator()
        md = gen.generate_markdown_report(sample_evaluations)
        assert "分布统计" in md
        assert "均值" in md

    def test_markdown_contains_boxplot(self, sample_evaluations):
        """Markdown 包含箱线图数据"""
        gen = ReportGenerator()
        md = gen.generate_markdown_report(sample_evaluations)
        assert "分数离散度" in md
        assert "|" in md  # 表格分隔符

    def test_write_markdown_to_file(self, sample_evaluations):
        """写入 Markdown 文件"""
        gen = ReportGenerator()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.md"
            written = gen.write_markdown_report(sample_evaluations, path)
            assert written.exists()
            assert "KPI" in written.read_text(encoding="utf-8")


class TestReportGeneratorEdgeCases:
    """边界测试"""

    def test_custom_dashboard_data(self, sample_evaluations):
        """自定义仪表盘数据"""
        gen = ReportGenerator()
        custom = VisualizationService.generate_dashboard(sample_evaluations)
        html = gen.generate_html_report(sample_evaluations, custom)
        assert "<!DOCTYPE html>" in html

    def test_evaluations_truncated(self, sample_evaluations):
        """大量评估时截断到 500"""
        many = sample_evaluations * 300
        gen = ReportGenerator()
        data = gen.generate_json_data(many)
        assert len(data["evaluations"]) <= 500
