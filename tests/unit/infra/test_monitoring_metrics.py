"""
Prometheus Metrics 专项测试
测试目标：验证Prometheus指标的注册、初始化、暴露功能
关键发现：
1. 使用全局CollectorRegistry
2. 支持多种指标类型：Counter/Gauge/Histogram
3. 暴露格式为prometheus文本格式
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


class TestMetricsRegistration:
    """指标注册测试"""

    def test_evaluation_metrics_registered(self):
        """场景：评测指标应已注册"""
        from src.infra.monitoring.metrics import (
            EVALUATION_COUNTER,
            EVALUATION_ERRORS,
            EVALUATION_LATENCY,
        )

        assert EVALUATION_COUNTER is not None
        assert EVALUATION_LATENCY is not None
        assert EVALUATION_ERRORS is not None

    def test_task_metrics_registered(self):
        """场景：任务指标应已注册"""
        from src.infra.monitoring.metrics import (
            TASK_EXECUTION_TIME,
            TASK_QUEUE_SIZE,
        )

        assert TASK_QUEUE_SIZE is not None
        assert TASK_EXECUTION_TIME is not None

    def test_buffer_metrics_registered(self):
        """场景：缓冲区指标应已注册"""
        from src.infra.monitoring.metrics import (
            BUFFER_FLUSH_COUNT,
            BUFFER_FLUSH_LATENCY,
            BUFFER_SIZE,
        )

        assert BUFFER_SIZE is not None
        assert BUFFER_FLUSH_COUNT is not None
        assert BUFFER_FLUSH_LATENCY is not None

    def test_db_metrics_registered(self):
        """场景：数据库指标应已注册"""
        from src.infra.monitoring.metrics import DB_CONNECTIONS, DB_QUERY_LATENCY

        assert DB_CONNECTIONS is not None
        assert DB_QUERY_LATENCY is not None

    def test_rate_limiter_metrics_registered(self):
        """场景：限流指标应已注册"""
        from src.infra.monitoring.metrics import (
            RATE_LIMITER_BLOCKED,
            RATE_LIMITER_TOKENS,
        )

        assert RATE_LIMITER_TOKENS is not None
        assert RATE_LIMITER_BLOCKED is not None

    def test_global_registry_exists(self):
        """场景：全局注册器应存在"""
        from src.infra.monitoring.metrics import registry

        assert registry is not None


class TestMetricsUsage:
    """指标使用测试"""

    def test_evaluation_counter_increment(self):
        """场景：评测计数器递增"""
        from src.infra.monitoring.metrics import EVALUATION_COUNTER

        # 记录一次评测
        EVALUATION_COUNTER.labels(domain="test", status="success").inc()

        # 验证指标存在(通过expose_metrics)
        output = self._get_metrics_output()
        assert "evaluation_total" in output

    def test_evaluation_latency_observe(self):
        """场景：评测延迟观察"""
        from src.infra.monitoring.metrics import EVALUATION_LATENCY

        # 记录一次延迟
        EVALUATION_LATENCY.labels(domain="test", status="success").observe(0.5)

        output = self._get_metrics_output()
        assert "evaluation_latency_seconds" in output

    def test_evaluation_error_counter(self):
        """场景：评测错误计数"""
        from src.infra.monitoring.metrics import EVALUATION_ERRORS

        EVALUATION_ERRORS.labels(domain="test", error_type="timeout").inc()

        output = self._get_metrics_output()
        assert "evaluation_errors_total" in output

    def test_task_queue_size_gauge(self):
        """场景：任务队列大小"""
        from src.infra.monitoring.metrics import TASK_QUEUE_SIZE

        TASK_QUEUE_SIZE.labels(queue_name="default").set(10)

        output = self._get_metrics_output()
        assert "task_queue_size" in output

    def test_buffer_size_gauge(self):
        """场景：缓冲区大小"""
        from src.infra.monitoring.metrics import BUFFER_SIZE

        BUFFER_SIZE.set(50)

        output = self._get_metrics_output()
        assert "buffer_size" in output

    def test_db_connections_gauge(self):
        """场景：数据库连接数"""
        from src.infra.monitoring.metrics import DB_CONNECTIONS

        DB_CONNECTIONS.labels(status="active").set(5)

        output = self._get_metrics_output()
        assert "db_connections" in output

    def test_rate_limiter_tokens(self):
        """场景：限流令牌数"""
        from src.infra.monitoring.metrics import RATE_LIMITER_TOKENS

        RATE_LIMITER_TOKENS.labels(limiter_name="default").set(100)

        output = self._get_metrics_output()
        assert "rate_limiter_tokens" in output

    def test_rate_limiter_blocked(self):
        """场景：限流阻塞数"""
        from src.infra.monitoring.metrics import RATE_LIMITER_BLOCKED

        RATE_LIMITER_BLOCKED.labels(limiter_name="default").inc()

        output = self._get_metrics_output()
        assert "rate_limiter_blocked_total" in output

    def _get_metrics_output(self) -> str:
        """获取metrics输出"""
        from src.infra.monitoring.metrics import expose_metrics

        return expose_metrics()


class TestExposeMetrics:
    """expose_metrics 函数测试"""

    def test_expose_metrics_returns_text(self):
        """场景：返回文本格式"""
        from src.infra.monitoring.metrics import expose_metrics

        output = expose_metrics()

        # 应该是字符串
        assert isinstance(output, str)
        # 应包含Prometheus的HELP注释
        assert "# HELP" in output or "# TYPE" in output

    def test_expose_metrics_contains_all_indicators(self):
        """场景：应包含所有指标"""
        from src.infra.monitoring.metrics import expose_metrics

        output = expose_metrics()

        # 验证一些核心指标存在
        assert "evaluation" in output
        assert "task" in output or "buffer" in output


class TestMetricsNegativeCases:
    """负向测试 - 错误处理"""

    def test_increment_invalid_labels(self):
        """场景：无效标签应能处理"""
        from src.infra.monitoring.metrics import EVALUATION_COUNTER

        # 使用任意字符串作为label
        EVALUATION_COUNTER.labels(domain="custom_value", status="custom").inc()

        # 不应崩溃
        assert True

    def test_observe_negative_value(self):
        """场景：观察负值不应崩溃"""
        from src.infra.monitoring.metrics import EVALUATION_LATENCY

        # observe 应该能处理任何float
        EVALUATION_LATENCY.labels(domain="test", status="ok").observe(-1.0)

        assert True


class TestMetricsBoundaryCases:
    """边界测试"""

    def _get_metrics_output(self) -> str:
        """获取metrics输出"""
        from src.infra.monitoring.metrics import expose_metrics

        return expose_metrics()

    def test_zero_value_gauge(self):
        """场景：Gauge值为0"""
        from src.infra.monitoring.metrics import BUFFER_SIZE

        BUFFER_SIZE.set(0)

        output = self._get_metrics_output()
        assert "buffer_size" in output

    def test_large_value(self):
        """场景：大数值"""
        from src.infra.monitoring.metrics import TASK_QUEUE_SIZE

        TASK_QUEUE_SIZE.labels(queue_name="big").set(1000000)

        output = self._get_metrics_output()
        assert "task_queue_size" in output

    def test_multiple_labels(self):
        """场景：多种labels组合"""
        from src.infra.monitoring.metrics import EVALUATION_COUNTER

        # 不同domain和status组合
        for domain in ["finance", "code", "qa"]:
            for status in ["success", "failed"]:
                EVALUATION_COUNTER.labels(domain=domain, status=status).inc()

        output = self._get_metrics_output()
        assert "evaluation_total" in output
