"""
成本治理模块单元测试 - 带有效断言
覆盖: 成本计算、预算检查、指标统计、模型排序
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.infra.cost_governance import CostGovernance, CostMetrics, CostRecord


class TestCostCalculation:
    """成本计算单元测试"""

    def test_calculate_cost_gpt4(self):
        """GPT-4 成本计算应准确"""
        cg = CostGovernance()
        cost = cg.calculate_cost("gpt-4", 1000, 500)
        expected = 1000 * 0.00003 + 500 * 0.00006
        assert cost == pytest.approx(expected, 0.00001)

    def test_calculate_cost_gpt35(self):
        """GPT-3.5 成本计算应准确"""
        cg = CostGovernance()
        cost = cg.calculate_cost("gpt-3.5-turbo", 1000, 500)
        expected = 1000 * 0.0000015 + 500 * 0.000002
        assert cost == pytest.approx(expected, 0.00001)

    def test_calculate_cost_unknown_model_uses_default(self):
        """未知模型应使用默认费率"""
        cg = CostGovernance()
        cost = cg.calculate_cost("unknown-model", 1000, 500)
        expected = 1000 * 0.000002 + 500 * 0.000002
        assert cost == pytest.approx(expected, 0.00001)

    def test_calculate_cost_case_insensitive(self):
        """模型名应大小写不敏感"""
        cg = CostGovernance()
        cost1 = cg.calculate_cost("GPT-4", 1000, 500)
        cost2 = cg.calculate_cost("gpt-4", 1000, 500)
        assert cost1 == cost2

    def test_calculate_cost_zero_tokens(self):
        """零 token 成本应为 0"""
        cg = CostGovernance()
        cost = cg.calculate_cost("gpt-4", 0, 0)
        assert cost == 0.0


class TestRecordUsage:
    """记录使用单元测试"""

    def test_record_usage_returns_cost_record(self):
        """记录应返回 CostRecord 对象"""
        cg = CostGovernance()
        record = cg.record_usage("req_1", "gpt-4", 100, 50, 200.0)
        assert isinstance(record, CostRecord)
        assert record.record_id == "req_1"
        assert record.model_name == "gpt-4"

    def test_record_usage_calculates_cost(self):
        """记录应自动计算成本"""
        cg = CostGovernance()
        record = cg.record_usage("req_1", "gpt-4", 1000, 500)
        expected_cost = 1000 * 0.00003 + 500 * 0.00006
        assert record.cost_usd == pytest.approx(expected_cost, 0.00001)

    def test_record_usage_stores_in_records(self):
        """记录应被添加到 records 列表"""
        cg = CostGovernance()
        cg.record_usage("req_1", "gpt-4", 100, 50)
        assert len(cg.records) == 1
        cg.record_usage("req_2", "gpt-4", 200, 100)
        assert len(cg.records) == 2

    def test_record_usage_total_tokens(self):
        """总 token 数应等于 prompt + completion"""
        cg = CostGovernance()
        record = cg.record_usage("req_1", "gpt-4", 100, 50)
        assert record.usage.total_tokens == 150

    def test_record_request_simplified(self):
        """简化记录方法应正常工作"""
        cg = CostGovernance()
        record = cg.record_request(100, 50, 0.003, "gpt-4", 150.0)
        assert record.record_id == "req_0"
        assert record.model_name == "gpt-4"
        assert record.cost_usd == 0.003
        assert record.latency_ms == 150.0
        assert record.usage.prompt_tokens == 100
        assert record.usage.completion_tokens == 50


class TestMetricsCalculation:
    """指标统计单元测试"""

    def test_get_metrics_empty_records(self):
        """无记录时应返回零值指标"""
        cg = CostGovernance()
        metrics = cg.get_metrics()
        assert isinstance(metrics, CostMetrics)
        assert metrics.daily_cost_usd == 0.0
        assert metrics.total_requests == 0
        assert metrics.avg_latency_ms == 0.0

    def test_get_metrics_daily_cost(self):
        """日成本应只统计 24 小时内记录"""
        cg = CostGovernance()
        # 添加一条当前记录
        cg.record_request(1000, 500, 1.0, "gpt-4", 100.0)
        metrics = cg.get_metrics()
        assert metrics.daily_cost_usd == pytest.approx(1.0, 0.01)
        assert metrics.total_requests == 1

    def test_get_metrics_latency_percentiles(self):
        """延迟分位数计算应准确"""
        cg = CostGovernance()
        for i in range(100):
            cg.record_request(10, 10, 0.001, "gpt-4", float(i))
        metrics = cg.get_metrics()
        assert metrics.avg_latency_ms == pytest.approx(49.5, 0.1)
        assert metrics.p50_latency_ms == 50.0
        assert metrics.p95_latency_ms == 95.0
        assert metrics.p99_latency_ms == 99.0

    def test_get_metrics_avg_tokens(self):
        """平均 token 数应准确"""
        cg = CostGovernance()
        cg.record_request(100, 100, 0.001, "gpt-4", 100.0)
        cg.record_request(200, 200, 0.002, "gpt-4", 200.0)
        metrics = cg.get_metrics()
        assert metrics.avg_tokens_per_request == 300.0

    def test_get_metrics_with_hours_filter(self):
        """小时过滤应生效"""
        cg = CostGovernance()
        cg.record_request(100, 100, 1.0, "gpt-4", 100.0)
        metrics = cg.get_metrics(hours=1)
        assert metrics.total_requests == 1
        metrics = cg.get_metrics(hours=0)
        assert metrics.total_requests == 0


class TestBudgetCheck:
    """预算检查单元测试"""

    def test_check_budget_within_limit(self):
        """预算内应返回 ok"""
        cg = CostGovernance(daily_cost_limit=100.0)
        cg.record_request(100, 100, 10.0, "gpt-4", 100.0)
        result = cg.check_budget()
        assert result["daily_budget_ok"] is True
        assert result["daily_usage_percent"] == pytest.approx(10.0, 0.1)

    def test_check_budget_exceeds_limit(self):
        """超预算应返回 not ok"""
        cg = CostGovernance(daily_cost_limit=10.0)
        cg.record_request(100, 100, 15.0, "gpt-4", 100.0)
        result = cg.check_budget()
        assert result["daily_budget_ok"] is False
        assert result["daily_usage_percent"] == pytest.approx(150.0, 0.1)

    def test_check_budget_zero_limit(self):
        """零预算限制应始终返回 not ok"""
        cg = CostGovernance(daily_cost_limit=0.0)
        cg.record_request(100, 100, 0.0, "gpt-4", 100.0)
        result = cg.check_budget()
        assert result["daily_budget_ok"] is False


class TestTopModelsAndRequests:
    """模型排序和请求排序单元测试"""

    def test_get_top_models_by_cost(self):
        """应按成本降序排列模型"""
        cg = CostGovernance()
        cg.record_request(100, 100, 5.0, "model-a", 100.0)
        cg.record_request(100, 100, 10.0, "model-b", 200.0)
        cg.record_request(100, 100, 3.0, "model-c", 50.0)
        top = cg.get_top_models_by_cost()
        assert len(top) == 3
        assert top[0]["model_name"] == "model-b"
        assert top[0]["total_cost"] == 10.0
        assert top[1]["model_name"] == "model-a"
        assert top[2]["model_name"] == "model-c"

    def test_get_top_models_limit(self):
        """limit 参数应限制返回数量"""
        cg = CostGovernance()
        for i in range(10):
            cg.record_request(100, 100, float(i), f"model-{i}", 100.0)
        top = cg.get_top_models_by_cost(limit=3)
        assert len(top) == 3

    def test_get_top_requests_by_latency(self):
        """应按延迟降序排列请求"""
        cg = CostGovernance()
        cg.record_request(100, 100, 1.0, "gpt-4", 300.0)
        cg.record_request(100, 100, 1.0, "gpt-4", 100.0)
        cg.record_request(100, 100, 1.0, "gpt-4", 200.0)
        top = cg.get_top_requests_by_latency()
        assert top[0].latency_ms == 300.0
        assert top[1].latency_ms == 200.0
        assert top[2].latency_ms == 100.0

    def test_get_top_requests_limit(self):
        """limit 参数应限制返回数量"""
        cg = CostGovernance()
        for i in range(20):
            cg.record_request(100, 100, 1.0, "gpt-4", float(i))
        top = cg.get_top_requests_by_latency(limit=5)
        assert len(top) == 5


class TestCostGovernanceDefaults:
    """默认值单元测试"""

    def test_default_limits(self):
        """默认限制应合理"""
        cg = CostGovernance()
        assert cg.daily_cost_limit == 100.0
        assert cg.weekly_cost_limit == 500.0
        assert cg.monthly_cost_limit == 2000.0
        assert cg.hourly_request_limit == 10000

    def test_custom_limits(self):
        """自定义限制应生效"""
        cg = CostGovernance(
            daily_cost_limit=50.0, weekly_cost_limit=200.0, monthly_cost_limit=1000.0
        )
        assert cg.daily_cost_limit == 50.0
        assert cg.weekly_cost_limit == 200.0
        assert cg.monthly_cost_limit == 1000.0

    def test_model_costs_dict_not_empty(self):
        """模型成本表不应为空"""
        cg = CostGovernance()
        assert len(cg.MODEL_COSTS) > 0
        assert "gpt-4" in cg.MODEL_COSTS
        assert "default" in cg.MODEL_COSTS
