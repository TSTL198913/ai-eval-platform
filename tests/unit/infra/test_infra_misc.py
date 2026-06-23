"""
Infra杂项模块专项测试
测试目标：验证seed_data、tracing、benchmark_report等模块
"""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.infra.analytics.benchmark_report import (
    BenchmarkReport,
    build_benchmark_report,
    format_benchmark_summary,
    percentile,
    save_benchmark_report,
)
from src.infra.db.seed_data import seed_db
from src.infra.tracing import generate_trace_id, trace_id_var


class TestTracing:
    """Tracing追踪模块测试"""

    def test_generate_trace_id(self):
        """生成trace_id应返回8位字符串"""
        trace_id = generate_trace_id()
        assert isinstance(trace_id, str)
        assert len(trace_id) == 8

    def test_trace_id_var_default(self):
        """trace_id_var默认值应为'system'"""
        assert trace_id_var.get() == "system"

    def test_trace_id_var_set_and_get(self):
        """设置和获取trace_id_var"""
        token = trace_id_var.set("test_trace_id")
        assert trace_id_var.get() == "test_trace_id"
        trace_id_var.reset(token)
        assert trace_id_var.get() == "system"


class TestBenchmarkReport:
    """BenchmarkReport基准测试报告测试"""

    def test_percentile_empty(self):
        """空列表应返回0"""
        result = percentile([], 0.5)
        assert result == 0.0

    def test_percentile_single_value(self):
        """单值列表应返回该值"""
        result = percentile([100], 0.5)
        assert result == 100

    def test_percentile_normal(self):
        """正常列表应正确计算百分位数"""
        values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        assert percentile(values, 0.5) == 60
        assert percentile(values, 0.9) == 100

    def test_percentile_boundary(self):
        """边界百分位数"""
        values = [100, 200, 300]
        assert percentile(values, 1.0) == 300

    def test_report_construction(self):
        """构造BenchmarkReport"""
        report = BenchmarkReport(
            total_cases=100,
            success_count=85,
            success_rate=0.85,
            total_time_ms=10000.0,
            avg_latency_ms=100.0,
            p50_latency_ms=90.0,
            p95_latency_ms=150.0,
            p99_latency_ms=200.0,
            tps=10.0,
        )

        assert report.total_cases == 100
        assert report.success_rate == 0.85
        assert report.tps == 10.0

    def test_report_to_dict(self):
        """to_dict应返回正确的字典"""
        report = BenchmarkReport(
            total_cases=10,
            success_count=8,
            success_rate=0.8,
            total_time_ms=1000.0,
            avg_latency_ms=100.0,
            p50_latency_ms=100.0,
            p95_latency_ms=150.0,
            p99_latency_ms=200.0,
            tps=10.0,
        )

        result = report.to_dict()
        assert result["total_cases"] == 10
        assert result["success_rate"] == 0.8
        assert "generated_at" in result

    def test_build_benchmark_report(self):
        """构建基准测试报告"""
        latencies = [100, 120, 80, 150, 90]
        report = build_benchmark_report(latencies, 4, 5)

        assert report.total_cases == 5
        assert report.success_count == 4
        assert report.success_rate == 0.8
        assert report.avg_latency_ms == 108.0

    def test_build_benchmark_report_empty_latencies(self):
        """空延迟列表应正确处理"""
        report = build_benchmark_report([], 0, 0)

        assert report.avg_latency_ms == 0.0
        assert report.tps == 0.0

    def test_build_benchmark_report_zero_total_time(self):
        """总时间为0时TPS应为0"""
        report = build_benchmark_report([0, 0, 0], 3, 3)

        assert report.tps == 0.0

    def test_format_benchmark_summary(self):
        """格式化报告摘要"""
        report = BenchmarkReport(
            total_cases=100,
            success_count=85,
            success_rate=0.85,
            total_time_ms=10000.0,
            avg_latency_ms=100.0,
            p50_latency_ms=90.0,
            p95_latency_ms=150.0,
            p99_latency_ms=200.0,
            tps=10.0,
        )

        summary = format_benchmark_summary(report)
        assert "Benchmark Report" in summary
        assert "Total Cases" in summary
        assert "Success Rate" in summary

    def test_save_benchmark_report(self):
        """保存基准测试报告"""
        report = BenchmarkReport(
            total_cases=10,
            success_count=8,
            success_rate=0.8,
            total_time_ms=1000.0,
            avg_latency_ms=100.0,
            p50_latency_ms=100.0,
            p95_latency_ms=150.0,
            p99_latency_ms=200.0,
            tps=10.0,
        )

        with patch("src.infra.analytics.benchmark_report.Path") as mock_path_class:
            mock_path = MagicMock()
            mock_path_class.return_value = mock_path
            mock_path.__str__.return_value = "output/report.json"
            mock_path.parent.mkdir.return_value = None
            mock_path.write_text.return_value = None

            result = save_benchmark_report(report, "output/report.json")

            assert result == "output/report.json"
            mock_path.write_text.assert_called_once()


class TestSeedData:
    """SeedData种子数据测试"""

    def test_seed_db(self):
        """生成种子数据"""
        with patch("src.infra.db.seed_data.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db

            with patch("builtins.print") as mock_print:
                seed_db()

                assert mock_db.add.call_count == 10
                mock_db.commit.assert_called_once()
                mock_print.assert_called_once()
