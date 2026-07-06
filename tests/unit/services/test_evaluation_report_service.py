"""测试 EvaluationReportService 评估统计报表服务"""

import pytest
import os
from unittest.mock import MagicMock, patch


class TestEvaluationReportService:
    """测试评估统计报表服务"""

    def test_get_report_types(self):
        """获取支持的报表类型"""
        from src.domain.services.evaluation_report_service import evaluation_report_service

        types = evaluation_report_service.get_report_types()
        assert "summary" in types
        assert "trend" in types
        assert "model_comparison" in types
        assert "evaluator_performance" in types
        assert "detail" in types

    @patch("src.domain.services.evaluation_report_service.EvaluationRepository")
    def test_generate_summary_report(self, mock_repo):
        """生成汇总报表"""
        mock_repo_instance = MagicMock()
        mock_repo_instance.search.return_value = [
            {
                "id": 1,
                "case_id": "test-1",
                "model_name": "gpt-4",
                "adapter_name": "general",
                "status": "SUCCESS",
                "latency_ms": 1000.0,
                "score": 0.85,
                "created_at": "2024-01-01T00:00:00",
            },
            {
                "id": 2,
                "case_id": "test-2",
                "model_name": "gpt-4",
                "adapter_name": "qa",
                "status": "SUCCESS",
                "latency_ms": 2000.0,
                "score": 0.90,
                "created_at": "2024-01-01T00:01:00",
            },
        ]
        mock_repo.return_value = mock_repo_instance

        from src.domain.services.evaluation_report_service import EvaluationReportService

        service = EvaluationReportService()
        report = service.generate_report("summary")

        assert report["report_type"] == "summary"
        assert report["summary"]["total_evaluations"] == 2
        assert report["summary"]["unique_models"] == 1
        assert report["summary"]["unique_evaluators"] == 2
        assert report["score_statistics"]["average_score"] == 0.875
        assert report["latency_statistics"]["average_ms"] == 1500.0

    @patch("src.domain.services.evaluation_report_service.EvaluationRepository")
    def test_generate_summary_report_empty(self, mock_repo):
        """生成空汇总报表"""
        mock_repo_instance = MagicMock()
        mock_repo_instance.search.return_value = []
        mock_repo.return_value = mock_repo_instance

        from src.domain.services.evaluation_report_service import EvaluationReportService

        service = EvaluationReportService()
        report = service.generate_report("summary")

        assert "message" in report
        assert report["message"] == "没有找到匹配的数据"

    @patch("src.domain.services.evaluation_report_service.EvaluationRepository")
    def test_generate_trend_report(self, mock_repo):
        """生成趋势报表"""
        mock_repo_instance = MagicMock()
        mock_repo_instance.search.return_value = [
            {"id": 1, "case_id": "test-1", "score": 0.85, "latency_ms": 1000.0, "created_at": "2024-01-01T00:00:00"},
            {"id": 2, "case_id": "test-2", "score": 0.90, "latency_ms": 1500.0, "created_at": "2024-01-01T00:00:00"},
            {"id": 3, "case_id": "test-3", "score": 0.80, "latency_ms": 1200.0, "created_at": "2024-01-02T00:00:00"},
        ]
        mock_repo.return_value = mock_repo_instance

        from src.domain.services.evaluation_report_service import EvaluationReportService

        service = EvaluationReportService()
        report = service.generate_report("trend")

        assert report["report_type"] == "trend"
        assert report["total_days"] == 2
        assert len(report["trend_data"]) == 2

    @patch("src.domain.services.evaluation_report_service.EvaluationRepository")
    def test_generate_model_comparison_report(self, mock_repo):
        """生成模型对比报表"""
        mock_repo_instance = MagicMock()
        mock_repo_instance.search.return_value = [
            {"id": 1, "case_id": "test-1", "model_name": "gpt-4", "score": 0.85, "latency_ms": 1000.0, "status": "SUCCESS"},
            {"id": 2, "case_id": "test-2", "model_name": "gpt-4", "score": 0.90, "latency_ms": 1200.0, "status": "SUCCESS"},
            {"id": 3, "case_id": "test-3", "model_name": "claude-3", "score": 0.88, "latency_ms": 800.0, "status": "SUCCESS"},
        ]
        mock_repo.return_value = mock_repo_instance

        from src.domain.services.evaluation_report_service import EvaluationReportService

        service = EvaluationReportService()
        report = service.generate_report("model_comparison")

        assert report["report_type"] == "model_comparison"
        assert report["total_models"] == 2
        assert len(report["model_comparison"]) == 2

    @patch("src.domain.services.evaluation_report_service.EvaluationRepository")
    def test_generate_evaluator_performance_report(self, mock_repo):
        """生成评估器性能报表"""
        mock_repo_instance = MagicMock()
        mock_repo_instance.search.return_value = [
            {"id": 1, "case_id": "test-1", "adapter_name": "general", "score": 0.85, "latency_ms": 1000.0, "status": "SUCCESS"},
            {"id": 2, "case_id": "test-2", "adapter_name": "general", "score": 0.90, "latency_ms": 1200.0, "status": "SUCCESS"},
            {"id": 3, "case_id": "test-3", "adapter_name": "qa", "score": 0.88, "latency_ms": 800.0, "status": "SUCCESS"},
            {"id": 4, "case_id": "test-4", "adapter_name": "qa", "score": 0.0, "latency_ms": 500.0, "status": "ERROR"},
        ]
        mock_repo.return_value = mock_repo_instance

        from src.domain.services.evaluation_report_service import EvaluationReportService

        service = EvaluationReportService()
        report = service.generate_report("evaluator_performance")

        assert report["report_type"] == "evaluator_performance"
        assert report["total_evaluators"] == 2

    @patch("src.domain.services.evaluation_report_service.EvaluationRepository")
    def test_generate_detail_report(self, mock_repo):
        """生成详细报表"""
        mock_repo_instance = MagicMock()
        mock_repo_instance.search.return_value = [
            {"id": 1, "case_id": "test-1", "score": 0.85, "created_at": "2024-01-01T00:00:00"},
            {"id": 2, "case_id": "test-2", "score": 0.90, "created_at": "2024-01-01T00:01:00"},
        ]
        mock_repo.return_value = mock_repo_instance

        from src.domain.services.evaluation_report_service import EvaluationReportService

        service = EvaluationReportService()
        report = service.generate_report("detail")

        assert report["report_type"] == "detail"
        assert report["total_records"] == 2
        assert len(report["records"]) == 2

    @patch("src.domain.services.evaluation_report_service.EvaluationRepository")
    def test_export_report_json(self, mock_repo):
        """导出报表为 JSON"""
        mock_repo_instance = MagicMock()
        mock_repo_instance.search.return_value = []
        mock_repo.return_value = mock_repo_instance

        from src.domain.services.evaluation_report_service import EvaluationReportService

        service = EvaluationReportService()
        filepath = service.export_report("summary", format="json")
        assert os.path.exists(filepath)
        os.remove(filepath)

    @patch("src.domain.services.evaluation_report_service.EvaluationRepository")
    def test_export_report_csv(self, mock_repo):
        """导出报表为 CSV"""
        mock_repo_instance = MagicMock()
        mock_repo_instance.search.return_value = [
            {"id": 1, "case_id": "test-1", "model_name": "test", "adapter_name": "test", "status": "SUCCESS", "latency_ms": 1000.0, "score": 0.85, "created_at": "2024-01-01T00:00:00"},
        ]
        mock_repo.return_value = mock_repo_instance

        from src.domain.services.evaluation_report_service import EvaluationReportService

        service = EvaluationReportService()
        filepath = service.export_report("summary", format="csv")
        assert os.path.exists(filepath)
        os.remove(filepath)

    def test_report_type_enum(self):
        """测试报表类型枚举"""
        from src.domain.services.evaluation_report_service import ReportType

        assert ReportType.SUMMARY.value == "summary"
        assert ReportType.TREND.value == "trend"
        assert ReportType.MODEL_COMPARISON.value == "model_comparison"
        assert ReportType.EVALUATOR_PERFORMANCE.value == "evaluator_performance"
        assert ReportType.DETAIL.value == "detail"

    def test_calculate_std(self):
        """测试标准差计算"""
        from src.domain.services.evaluation_report_service import EvaluationReportService

        service = EvaluationReportService()
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        std = service._calculate_std(values)
        assert abs(std - 1.4142) < 0.0001

    def test_calculate_percentile(self):
        """测试百分位数计算"""
        from src.domain.services.evaluation_report_service import EvaluationReportService

        service = EvaluationReportService()
        values = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
        p95 = service._calculate_percentile(values, 95)
        assert abs(p95 - 955) < 0.01

    def test_calculate_pass_rate(self):
        """测试通过率计算"""
        from src.domain.services.evaluation_report_service import EvaluationReportService

        service = EvaluationReportService()

        status_counts = {"SUCCESS": 80, "ERROR": 20}
        pass_rate = service._calculate_pass_rate(status_counts)
        assert pass_rate == 80.0

        status_counts = {"pass": 50, "fail": 50}
        pass_rate = service._calculate_pass_rate(status_counts)
        assert pass_rate == 50.0

        status_counts = {}
        pass_rate = service._calculate_pass_rate(status_counts)
        assert pass_rate == 0.0