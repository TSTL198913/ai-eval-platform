import time
from unittest.mock import patch

import pytest

from src.infra.cost_governance import CostGovernance, CostMetrics, CostRecord, TokenUsage


class TestCostGovernance:
    """成本治理模块测试"""

    def setup_method(self):
        self.governance = CostGovernance()
        self.governance.records = []

    def test_calculate_cost_gpt4(self):
        """测试GPT-4成本计算"""
        cost = self.governance.calculate_cost("gpt-4", 1000, 500)
        expected = (1000 * 0.00003) + (500 * 0.00006)
        assert cost == expected

    def test_calculate_cost_gpt35(self):
        """测试GPT-3.5成本计算"""
        cost = self.governance.calculate_cost("gpt-3.5-turbo", 1000, 500)
        expected = (1000 * 0.0000015) + (500 * 0.000002)
        assert cost == expected

    def test_calculate_cost_claude(self):
        """测试Claude成本计算"""
        cost = self.governance.calculate_cost("claude-3", 1000, 500)
        expected = (1000 * 0.000008) + (500 * 0.000024)
        assert cost == expected

    def test_calculate_cost_gemini(self):
        """测试Gemini成本计算"""
        cost = self.governance.calculate_cost("gemini-pro", 1000, 500)
        expected = (1000 * 0.000001) + (500 * 0.0000015)
        assert cost == expected

    def test_calculate_cost_default(self):
        """测试默认模型成本计算"""
        cost = self.governance.calculate_cost("unknown-model", 1000, 500)
        expected = (1000 * 0.000002) + (500 * 0.000002)
        assert cost == expected

    def test_calculate_cost_case_insensitive(self):
        """测试模型名大小写不敏感"""
        cost_lower = self.governance.calculate_cost("gpt-4", 1000, 500)
        cost_upper = self.governance.calculate_cost("GPT-4", 1000, 500)
        assert cost_lower == cost_upper

    def test_record_usage(self):
        """测试记录使用量"""
        record = self.governance.record_usage(
            record_id="r1",
            model_name="gpt-4",
            prompt_tokens=100,
            completion_tokens=50,
            latency_ms=200,
            request_type="evaluation",
        )

        assert record.record_id == "r1"
        assert record.model_name == "gpt-4"
        assert record.usage.prompt_tokens == 100
        assert record.usage.completion_tokens == 50
        assert record.usage.total_tokens == 150
        assert record.latency_ms == 200
        assert record.cost_usd > 0
        assert len(self.governance.records) == 1

    def test_record_usage_default_tokens(self):
        """测试默认token为0"""
        record = self.governance.record_usage(
            record_id="r2",
            model_name="gpt-4",
        )

        assert record.usage.total_tokens == 0
        assert record.cost_usd == 0

    def test_get_metrics_empty(self):
        """测试空记录指标"""
        metrics = self.governance.get_metrics()

        assert metrics.daily_cost_usd == 0
        assert metrics.total_requests == 0

    def test_get_metrics_with_records(self):
        """测试有记录时的指标"""
        now = time.time()
        self.governance.records = [
            CostRecord(
                record_id="r1",
                model_name="gpt-4",
                usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
                cost_usd=0.01,
                latency_ms=100,
                timestamp=now,
            ),
            CostRecord(
                record_id="r2",
                model_name="gpt-3.5-turbo",
                usage=TokenUsage(prompt_tokens=200, completion_tokens=100, total_tokens=300),
                cost_usd=0.005,
                latency_ms=200,
                timestamp=now,
            ),
        ]

        metrics = self.governance.get_metrics()

        assert metrics.daily_cost_usd == 0.015
        assert metrics.total_requests == 2
        assert metrics.avg_latency_ms == 150
        assert metrics.avg_tokens_per_request == 225

    def test_get_metrics_filtered_by_hours(self):
        """测试按小时过滤指标"""
        now = time.time()
        self.governance.records = [
            CostRecord(
                record_id="r1",
                model_name="gpt-4",
                usage=TokenUsage(total_tokens=100),
                cost_usd=0.01,
                latency_ms=100,
                timestamp=now,
            ),
            CostRecord(
                record_id="r2",
                model_name="gpt-4",
                usage=TokenUsage(total_tokens=100),
                cost_usd=0.01,
                latency_ms=200,
                timestamp=now - 7200,
            ),
        ]

        metrics = self.governance.get_metrics(hours=1)

        assert metrics.total_requests == 1
        assert metrics.daily_cost_usd == 0.01

    def test_check_budget(self):
        """测试预算检查"""
        now = time.time()
        self.governance.records = [
            CostRecord(
                record_id="r1",
                model_name="gpt-4",
                usage=TokenUsage(total_tokens=100),
                cost_usd=10.0,
                latency_ms=100,
                timestamp=now,
            ),
        ]

        result = self.governance.check_budget()

        assert result["daily_budget_ok"] is True
        assert "daily_usage_percent" in result

    def test_get_top_models_by_cost(self):
        """测试按成本排序的模型"""
        now = time.time()
        self.governance.records = [
            CostRecord(
                record_id="r1",
                model_name="gpt-4",
                usage=TokenUsage(total_tokens=100),
                cost_usd=0.05,
                latency_ms=100,
                timestamp=now,
            ),
            CostRecord(
                record_id="r2",
                model_name="gpt-3.5-turbo",
                usage=TokenUsage(total_tokens=100),
                cost_usd=0.01,
                latency_ms=200,
                timestamp=now,
            ),
        ]

        top_models = self.governance.get_top_models_by_cost(limit=5)

        assert len(top_models) == 2
        assert top_models[0]["model_name"] == "gpt-4"
        assert top_models[0]["total_cost"] == 0.05

    def test_get_top_requests_by_latency(self):
        """测试按延迟排序的请求"""
        now = time.time()
        self.governance.records = [
            CostRecord(
                record_id="r1",
                model_name="gpt-4",
                usage=TokenUsage(total_tokens=100),
                cost_usd=0.01,
                latency_ms=100,
                timestamp=now,
            ),
            CostRecord(
                record_id="r2",
                model_name="gpt-4",
                usage=TokenUsage(total_tokens=100),
                cost_usd=0.01,
                latency_ms=500,
                timestamp=now,
            ),
        ]

        top_requests = self.governance.get_top_requests_by_latency(limit=10)

        assert len(top_requests) == 2
        assert top_requests[0].record_id == "r2"
        assert top_requests[0].latency_ms == 500


class TestCostRecord:
    """成本记录模型测试"""

    def test_cost_record_defaults(self):
        """测试默认值"""
        record = CostRecord(
            record_id="r1",
            model_name="gpt-4",
        )

        assert record.usage.prompt_tokens == 0
        assert record.usage.completion_tokens == 0
        assert record.cost_usd == 0.0
        assert record.request_type == "evaluation"
        assert record.timestamp > 0


class TestCostMetrics:
    """成本指标模型测试"""

    def test_cost_metrics_defaults(self):
        """测试默认值"""
        metrics = CostMetrics()

        assert metrics.daily_cost_usd == 0.0
        assert metrics.total_requests == 0
        assert metrics.avg_latency_ms == 0.0