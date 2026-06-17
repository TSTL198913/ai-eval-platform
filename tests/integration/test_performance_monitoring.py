"""
性能监控与分析模块集成测试
覆盖性能监控、追踪、分析查询等核心功能
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from src.infra.monitoring.metrics import (
    registry,
    EVALUATION_LATENCY,
    EVALUATION_COUNTER,
    EVALUATION_ERRORS,
    TASK_QUEUE_SIZE,
    TASK_EXECUTION_TIME,
    BUFFER_SIZE,
    BUFFER_FLUSH_COUNT,
    DB_CONNECTIONS,
    RATE_LIMITER_TOKENS,
    expose_metrics,
)
from src.infra.monitoring.tracing import (
    SpanContext,
    Span,
    current_trace_id,
    current_span_id,
    TraceContext,
    Tracer,
    get_tracer,
    SpanContextCarrier,
)


class TestMetricsIntegration:
    """指标监控集成测试"""

    def test_registry_exists(self):
        """测试注册器存在"""
        assert registry is not None

    def test_evaluation_latency_histogram(self):
        """测试评测延迟直方图"""
        assert EVALUATION_LATENCY is not None
        # 测试记录
        EVALUATION_LATENCY.labels(domain="finance", status="success").observe(1.5)
        EVALUATION_LATENCY.labels(domain="finance", status="success").observe(2.0)

    def test_evaluation_counter(self):
        """测试评测计数器"""
        assert EVALUATION_COUNTER is not None
        # 测试增加计数
        EVALUATION_COUNTER.labels(domain="code", status="success").inc()
        EVALUATION_COUNTER.labels(domain="code", status="success").inc()

    def test_request_latency(self):
        """测试任务执行时间"""
        assert TASK_EXECUTION_TIME is not None
        TASK_EXECUTION_TIME.labels(task_name="test_task", status="success").observe(0.5)

    def test_request_counter(self):
        """测试任务执行计数器"""
        assert TASK_EXECUTION_TIME is not None
        # Histogram 没有 inc 方法，应该用 observe
        TASK_EXECUTION_TIME.labels(task_name="test_task", status="success").observe(0.6)


class TestTracingIntegration:
    """追踪集成测试"""

    def test_span_context(self):
        """测试Span上下文"""
        context = SpanContext(
            trace_id="test_trace_001",
            span_id="test_span_001",
        )
        assert context.trace_id == "test_trace_001"
        assert context.span_id == "test_span_001"
        assert context.sampled is True

    def test_span_creation(self):
        """测试Span创建"""
        import time

        span = Span(
            name="test_operation",
            span_id="span_001",
            trace_id="trace_001",
            parent_id=None,
            start_time=time.time(),
        )
        assert span.name == "test_operation"
        assert span.status == "OK"

    def test_span_set_attribute(self):
        """测试Span设置属性"""
        import time

        span = Span(
            name="test",
            span_id="span_001",
            trace_id="trace_001",
            parent_id=None,
            start_time=time.time(),
        )
        span.set_attribute("user_id", "user_001")
        assert span.attributes["user_id"] == "user_001"

    def test_span_add_event(self):
        """测试Span添加事件"""
        import time

        span = Span(
            name="test",
            span_id="span_001",
            trace_id="trace_001",
            parent_id=None,
            start_time=time.time(),
        )
        span.add_event("test_event", {"key": "value"})
        assert len(span.events) == 1
        assert span.events[0]["name"] == "test_event"

    def test_span_duration(self):
        """测试Span持续时间"""
        import time

        start = time.time()
        span = Span(
            name="test",
            span_id="span_001",
            trace_id="trace_001",
            parent_id=None,
            start_time=start,
        )
        span.end_time = start + 1.0
        assert span.duration == 1.0

    def test_context_var_tracing(self):
        """测试上下文变量追踪"""
        trace_id = current_trace_id.set("trace_001")
        assert current_trace_id.get() == "trace_001"
        current_trace_id.reset(trace_id)

    def test_context_var_span(self):
        """测试上下文变量Span"""
        span_id = current_span_id.set("span_001")
        assert current_span_id.get() == "span_001"
        current_span_id.reset(span_id)

    def test_trace_context_manager(self):
        """测试追踪上下文管理器"""
        tracer = Tracer("test_service")
        context = TraceContext(tracer, "test_operation")
        with context as trace:
            assert trace.span is not None
            assert trace.span.name == "test_operation"

    def test_tracer_get_tracer(self):
        """测试获取全局tracer"""
        tracer = get_tracer()
        assert tracer is not None
        assert tracer.service_name == "eval-platform"

    def test_span_context_carrier(self):
        """测试Span上下文传播载体"""
        span_context = SpanContext(
            trace_id="test_trace_001",
            span_id="test_span_001",
        )
        headers = SpanContextCarrier.inject(span_context)
        assert headers["x-trace-id"] == "test_trace_001"
        assert headers["x-parent-span-id"] == "test_span_001"

    def test_span_context_extract(self):
        """测试从headers提取Span上下文"""
        headers = {
            "x-trace-id": "test_trace_001",
            "x-parent-span-id": "test_span_001",
        }
        span_context = SpanContextCarrier.extract(headers)
        assert span_context is not None
        assert span_context.trace_id == "test_trace_001"
        assert span_context.parent_id == "test_span_001"

    def test_expose_metrics(self):
        """测试暴露指标"""
        metrics_output = expose_metrics()
        assert isinstance(metrics_output, str)
        assert len(metrics_output) > 0


class TestAnalyticsQueryIntegration:
    """分析查询集成测试"""

    def test_query_service_basic(self):
        """测试查询服务基本功能"""
        from src.infra.analytics.analytics import QueryService

        mock_db = MagicMock()
        service = QueryService(mock_db)
        assert service is not None

    def test_get_success_rate(self):
        """测试获取成功率"""
        from src.infra.analytics.analytics import QueryService

        mock_db = MagicMock()
        mock_db.query.return_value.count.return_value = 100
        mock_db.query.return_value.filter.return_value.count.return_value = 85

        service = QueryService(mock_db)
        rate = service.get_success_rate()
        assert rate == 85.0

    def test_get_avg_latency(self):
        """测试获取平均延迟"""
        from src.infra.analytics.analytics import QueryService

        mock_db = MagicMock()
        mock_db.query.return_value.scalar.return_value = 150.5

        service = QueryService(mock_db)
        latency = service.get_avg_latency()
        assert latency == 150.5

    def test_get_performance_report(self):
        """测试获取性能报告"""
        from src.infra.analytics.analytics import QueryService

        mock_db = MagicMock()
        mock_db.query.return_value.count.return_value = 100
        mock_db.query.return_value.filter.return_value.count.return_value = 90
        mock_db.query.return_value.scalar.return_value = 125.5

        service = QueryService(mock_db)
        report = service.get_performance_report()

        assert report["total_evals"] == 100
        assert report["success_rate"] == 0.9
        assert report["avg_latency_ms"] == 125.5


class TestPerformanceIntegration:
    """性能集成测试"""

    def test_metrics_with_tracing(self):
        """测试指标与追踪组合"""
        import time

        # 记录指标
        EVALUATION_LATENCY.labels(domain="test", status="success").observe(1.5)
        EVALUATION_COUNTER.labels(domain="test", status="success").inc()

        # 创建追踪
        tracer = Tracer("test_service")
        span = tracer.create_span("evaluation_test")
        assert span is not None
        tracer.end_span(span)

    def test_query_with_metrics(self):
        """测试查询与指标组合"""
        from src.infra.analytics.analytics import QueryService

        # 查询
        mock_db = MagicMock()
        mock_db.query.return_value.count.return_value = 10
        mock_db.query.return_value.filter.return_value.count.return_value = 8
        mock_db.query.return_value.scalar.return_value = 200.0

        service = QueryService(mock_db)
        report = service.get_performance_report()

        # 记录指标
        EVALUATION_COUNTER.labels(domain="batch", status="success").inc()
        EVALUATION_LATENCY.labels(domain="batch", status="success").observe(report["avg_latency_ms"] / 1000.0)

    def test_full_performance_flow(self):
        """测试完整性能流程"""
        import time

        from src.infra.analytics.analytics import QueryService

        # 1. 开始追踪
        tracer = Tracer("batch_service")
        with TraceContext(tracer, "batch_evaluation") as context:
            trace_id = context.span.trace_id

            # 2. 执行查询
            mock_db = MagicMock()
            mock_db.query.return_value.count.return_value = 50
            mock_db.query.return_value.filter.return_value.count.return_value = 45
            mock_db.query.return_value.scalar.return_value = 175.0

            service = QueryService(mock_db)
            report = service.get_performance_report()

            # 3. 记录指标
            EVALUATION_COUNTER.labels(domain="batch", status="success").inc()
            EVALUATION_LATENCY.labels(domain="batch", status="success").observe(report["avg_latency_ms"] / 1000.0)

        # 4. 验证结果
        assert report["total_evals"] == 50
        assert report["success_rate"] == 0.9


class TestMetricsEdgeCases:
    """指标边界情况测试"""

    def test_multiple_labels(self):
        """测试多标签指标"""
        EVALUATION_COUNTER.labels(domain="finance", status="success").inc()
        EVALUATION_COUNTER.labels(domain="code", status="success").inc()
        EVALUATION_COUNTER.labels(domain="finance", status="failed").inc()

    def test_histogram_observation(self):
        """测试直方图观察"""
        for i in range(100):
            EVALUATION_LATENCY.labels(domain="stress", status="success").observe(float(i) / 100.0)