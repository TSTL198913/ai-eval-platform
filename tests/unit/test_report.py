"""测试 infra/analytics/report.py"""

from unittest.mock import Mock, patch


class TestReportModule:
    """测试报告模块"""

    @patch("src.infra.analytics.report.SessionLocal")
    def test_main_function(self, mock_session_local):
        from src.infra.analytics.report import main

        mock_session = Mock()
        mock_session_local.return_value.__enter__.return_value = mock_session

        mock_service = Mock()
        mock_service.get_performance_report.return_value = {
            "total_evals": 100,
            "success_rate": 0.85,
            "avg_latency_ms": 150.5,
        }

        with patch("src.infra.analytics.report.QueryService", return_value=mock_service):
            main()
            mock_service.get_performance_report.assert_called_once()
