"""测试 infra/analytics/* 模块"""

from unittest.mock import Mock, patch

import pytest

from src.infra.analytics.analytics import QueryService


class TestQueryService:
    """测试查询服务"""

    @pytest.fixture
    def mock_db(self):
        return Mock()

    @pytest.fixture
    def service(self, mock_db):
        return QueryService(mock_db)

    def test_get_success_rate_with_data(self, service, mock_db):
        def build_query_chain(*args, **kwargs):
            chain = Mock()
            chain.count.return_value = 100
            filter_chain = Mock()
            filter_chain.count.return_value = 80
            chain.filter.return_value = filter_chain
            return chain

        mock_db.query.side_effect = build_query_chain

        rate = service.get_success_rate()
        assert rate == 80.0

    def test_get_success_rate_empty(self, service, mock_db):
        mock_query = Mock()
        mock_query.count.return_value = 0
        mock_db.query.return_value = mock_query

        rate = service.get_success_rate()
        assert rate == 0

    def test_get_success_rate_with_domain(self, service, mock_db):
        def build_query_chain(*args, **kwargs):
            chain = Mock()
            chain.count.return_value = 50
            filter_chain = Mock()
            filter_chain.count.return_value = 40
            chain.filter.return_value = filter_chain
            return chain

        mock_db.query.side_effect = build_query_chain

        rate = service.get_success_rate(domain="finance")
        assert rate == 80.0

    def test_get_avg_latency(self, service, mock_db):
        mock_db.query.return_value.scalar.return_value = 150.5
        avg = service.get_avg_latency()
        assert avg == 150.5

    def test_get_avg_latency_none(self, service, mock_db):
        mock_db.query.return_value.scalar.return_value = None
        avg = service.get_avg_latency()
        assert avg is None

    @patch("src.infra.analytics.analytics.EvaluationResultModel")
    def test_get_performance_report(self, mock_model, service, mock_db):
        call_count = [0]

        def mixed_query(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                chain = Mock()
                chain.count.return_value = 200
                return chain
            if call_count[0] == 2:
                chain = Mock()
                filter_chain = Mock()
                filter_chain.count.return_value = 180
                chain.filter.return_value = filter_chain
                return chain
            scalar = Mock()
            scalar.scalar.return_value = 120.0
            return scalar

        mock_db.query.side_effect = mixed_query

        report = service.get_performance_report()
        assert report["total_evals"] == 200
        assert report["success_rate"] == 0.9
        assert report["avg_latency_ms"] == 120.0

    @patch("src.infra.analytics.analytics.EvaluationResultModel")
    def test_get_performance_report_empty(self, mock_model, service, mock_db):
        chain = Mock()
        chain.count.return_value = 0
        scalar = Mock()
        scalar.scalar.return_value = 0.0
        call_count = [0]

        def mixed_query(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return chain
            return scalar

        mock_db.query.side_effect = mixed_query

        report = service.get_performance_report()
        assert report["total_evals"] == 0
        assert report["success_rate"] == 0.0
        assert report["avg_latency_ms"] == 0.0

    @patch("src.infra.analytics.analytics.EvaluationResultModel")
    def test_get_performance_by_domain(self, mock_model, service, mock_db):
        mock_result = [
            ("finance", 50, 100.0),
            ("code", 30, 150.0),
        ]
        group_chain = Mock()
        group_chain.all.return_value = mock_result
        mock_db.query.return_value.group_by.return_value = group_chain

        result = service.get_performance_by_domain()
        assert len(result) == 2
