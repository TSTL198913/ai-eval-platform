"""
Infra模块专项测试
测试目标：验证infra层各模块的核心功能
"""

import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.infra.analytics.analytics import QueryService
from src.infra.db.mapper import EvaluationMapper


class TestQueryService:
    """QueryService查询服务测试"""

    def test_get_success_rate_empty(self):
        """无数据时成功率应为0"""
        mock_db = MagicMock()
        mock_db.query.return_value.count.return_value = 0

        service = QueryService(mock_db)
        result = service.get_success_rate()

        assert result == 0

    def test_get_success_rate_with_data(self):
        """有数据时应正确计算成功率"""
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter_query = MagicMock()

        mock_db.query.return_value = mock_query
        mock_query.count.return_value = 100

        mock_query.filter.return_value = mock_filter_query
        mock_filter_query.count.return_value = 80

        service = QueryService(mock_db)
        result = service.get_success_rate()

        assert result == 80.0

    def test_get_success_rate_with_domain(self):
        """按领域过滤成功率"""
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter_query = MagicMock()

        mock_db.query.return_value = mock_query
        mock_query.count.return_value = 50
        mock_query.filter.return_value = mock_filter_query
        mock_filter_query.count.return_value = 40

        service = QueryService(mock_db)
        result = service.get_success_rate(domain="security")

        assert result == 80.0

    def test_get_avg_latency(self):
        """获取平均延迟"""
        mock_db = MagicMock()
        mock_db.query.return_value.scalar.return_value = 150.5

        service = QueryService(mock_db)
        result = service.get_avg_latency()

        assert result == 150.5

    def test_get_performance_report_empty(self):
        """无数据时性能报告"""
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.count.return_value = 0
        mock_query.scalar.return_value = None

        service = QueryService(mock_db)
        report = service.get_performance_report()

        assert report["total_evals"] == 0
        assert report["success_rate"] == 0.0
        assert report["avg_latency_ms"] == 0.0

    def test_get_performance_report_with_data(self):
        """有数据时性能报告"""
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter_query = MagicMock()

        mock_db.query.return_value = mock_query
        mock_query.count.return_value = 100
        mock_query.filter.return_value = mock_filter_query
        mock_filter_query.count.return_value = 85
        mock_query.scalar.return_value = 120.75

        service = QueryService(mock_db)
        report = service.get_performance_report()

        assert report["total_evals"] == 100
        assert report["success_rate"] == 0.85
        assert report["avg_latency_ms"] == 120.75

    def test_get_performance_by_domain(self):
        """按领域统计性能"""
        mock_db = MagicMock()
        mock_query = MagicMock()

        mock_db.query.return_value = mock_query
        mock_query.group_by.return_value.all.return_value = [
            (1, 50, 100.0),
            (2, 30, 150.0),
        ]

        service = QueryService(mock_db)
        result = service.get_performance_by_domain()

        assert len(result) == 2


class TestEvaluationMapper:
    """EvaluationMapper数据映射器测试"""

    def test_to_persistence_dict_with_model_dump(self):
        """将带model_dump方法的对象转换为持久化格式"""

        class MockModel:
            def model_dump(self):
                return {"score": 0.85, "status": "passed"}

        mapper = EvaluationMapper()
        result = mapper.to_persistence_dict(MockModel(), "case_001")

        assert result["score"] == 0.85
        assert result["status"] == "passed"
        assert result["case_id"] == "case_001"

    def test_to_persistence_dict_with_dict(self):
        """将字典转换为持久化格式"""
        mapper = EvaluationMapper()
        result = mapper.to_persistence_dict({"score": 0.9}, "case_002")

        assert result["score"] == 0.9
        assert result["case_id"] == "case_002"

    def test_to_persistence_dict_empty_case_id(self):
        """case_id为空时使用默认值"""
        mapper = EvaluationMapper()
        result = mapper.to_persistence_dict({}, "")

        assert result["case_id"] == "unknown_case_id"

    def test_to_persistence_dict_none_case_id(self):
        """case_id为None时使用默认值"""
        mapper = EvaluationMapper()
        result = mapper.to_persistence_dict({}, None)

        assert result["case_id"] == "unknown_case_id"
