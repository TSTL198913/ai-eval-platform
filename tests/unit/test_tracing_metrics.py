"""
追踪和指标单元测试
"""


import pytest

from src.tracing import (
    Tracer,
    SpanContext,
    SpanContextCarrier,
    TraceContext,
)
from src.metrics import (
    Counter,
    Gauge,
    Histogram,
    MetricsRegistry,
    get_registry,
)


class TestTracer:
    """追踪器测试"""

    def test_tracer_creation(self):
        """测试追踪器创建"""
        tracer = Tracer("test-service")

        assert tracer.service_name == "test-service"

    def test_create_span(self):
        """测试创建 Span"""
        tracer = Tracer("test-service")
        span = tracer.create_span("test_span")

        assert span.name == "test_span"
        assert span.trace_id is not None
        assert span.span_id is not None
        assert span.end_time is None

    def test_create_span_with_parent(self):
        """测试创建带父Span的子Span"""
        tracer = Tracer("test-service")
        parent = tracer.create_span("parent")

        child = tracer.create_span("child", parent_id=parent.span_id)

        assert child.parent_id == parent.span_id
        assert child.trace_id == parent.trace_id

    def test_span_finish(self):
        """测试 Span 结束"""
        tracer = Tracer("test-service")
        span = tracer.create_span("test")

        span.finish()

        assert span.end_time is not None
        assert span.end_time >= span.start_time

    def test_span_set_attribute(self):
        """测试设置 Span 属性"""
        tracer = Tracer("test-service")
        span = tracer.create_span("test")

        span.set_attribute("key", "value")

        assert span.attributes["key"] == "value"

    def test_span_add_event(self):
        """测试添加 Span 事件"""
        tracer = Tracer("test-service")
        span = tracer.create_span("test")

        span.add_event("test_event", {"key": "value"})

        assert len(span.events) == 1
        assert span.events[0]["name"] == "test_event"

    def test_span_set_status(self):
        """测试设置 Span 状态"""
        tracer = Tracer("test-service")
        span = tracer.create_span("test")

        span.set_status("ERROR", "Something went wrong")

        assert span.status == "ERROR"
        assert span.attributes["status.message"] == "Something went wrong"


class TestSpanContext:
    """Span 上下文测试"""

    def test_span_context_creation(self):
        """测试创建 Span 上下文"""
        ctx = SpanContext(
            trace_id="abc123",
            span_id="def456",
        )

        assert ctx.trace_id == "abc123"
        assert ctx.span_id == "def456"
        assert ctx.sampled is True

    def test_span_context_with_parent(self):
        """测试带父ID的上下文"""
        ctx = SpanContext(
            trace_id="abc123",
            span_id="def456",
            parent_id="parent789",
        )

        assert ctx.parent_id == "parent789"


class TestSpanContextCarrier:
    """Span 上下文传播测试"""

    def test_inject(self):
        """测试注入上下文到 headers"""
        ctx = SpanContext(
            trace_id="trace123",
            span_id="span456",
            parent_id="parent789",
        )

        headers = SpanContextCarrier.inject(ctx)

        assert headers["x-trace-id"] == "trace123"
        assert headers["x-parent-span-id"] == "span456"

    def test_extract(self):
        """测试从 headers 提取上下文"""
        headers = {
            "x-trace-id": "trace123",
            "x-parent-span-id": "span456",
        }

        ctx = SpanContextCarrier.extract(headers)

        assert ctx is not None
        assert ctx.trace_id == "trace123"
        assert ctx.parent_id == "span456"

    def test_extract_missing_header(self):
        """测试缺少 header 时返回 None"""
        ctx = SpanContextCarrier.extract({})

        assert ctx is None


class TestTraceContext:
    """追踪上下文管理器测试"""

    def test_trace_context(self):
        """测试追踪上下文"""
        tracer = Tracer("test-service")

        with TraceContext(tracer, "test_operation") as ctx:
            ctx.span.set_attribute("key", "value")

        assert ctx.span.end_time is not None
        assert ctx.span.attributes["key"] == "value"


class TestCounter:
    """计数器测试"""

    def test_counter_increment(self):
        """测试计数器增加"""
        counter = Counter("test_counter", "A test counter")

        counter.inc()
        counter.inc(5)

        assert counter.get() == 6

    def test_counter_with_labels(self):
        """测试带标签的计数器"""
        counter = Counter("test_counter", "A test counter", labels=["domain"])

        counter.inc(domain="finance")
        counter.inc(domain="text")
        counter.inc(domain="finance")

        assert counter.get(domain="finance") == 2
        assert counter.get(domain="text") == 1


class TestGauge:
    """仪表测试"""

    def test_gauge_increment(self):
        """测试仪表增加"""
        gauge = Gauge("test_gauge", "A test gauge")

        gauge.inc()
        gauge.inc(5)

        assert gauge.get() == 6

    def test_gauge_decrement(self):
        """测试仪表减少"""
        gauge = Gauge("test_gauge", "A test gauge")

        gauge.set(10)
        gauge.dec(3)

        assert gauge.get() == 7

    def test_gauge_set(self):
        """测试设置仪表值"""
        gauge = Gauge("test_gauge", "A test gauge")

        gauge.set(100)

        assert gauge.get() == 100


class TestHistogram:
    """直方图测试"""

    def test_histogram_observe(self):
        """测试记录观测值"""
        histogram = Histogram(
            "test_histogram",
            "A test histogram",
            buckets=[0.1, 0.5, 1.0, 5.0],
        )

        histogram.observe(0.3)
        histogram.observe(0.8)
        histogram.observe(2.0)

        stats = histogram.get_stats()

        assert stats["count"] == 3
        assert stats["sum"] == 3.1

    def test_histogram_buckets(self):
        """测试直方图桶"""
        histogram = Histogram(
            "test_histogram",
            "A test histogram",
            buckets=[0.1, 0.5, 1.0],
        )

        histogram.observe(0.05)  # < 0.1
        histogram.observe(0.3)   # < 0.5
        histogram.observe(0.8)   # < 1.0
        histogram.observe(2.0)   # >= 1.0

        stats = histogram.get_stats()

        assert stats["buckets"]["le_0.1"] == 1
        assert stats["buckets"]["le_0.5"] == 2
        assert stats["buckets"]["le_1.0"] == 3


class TestMetricsRegistry:
    """指标注册中心测试"""

    def test_register_counter(self):
        """测试注册计数器"""
        registry = MetricsRegistry()

        counter = registry.register_counter("test_counter", "A test counter")

        assert counter is not None
        assert registry.get_metric("test_counter") is counter

    def test_register_gauge(self):
        """测试注册仪表"""
        registry = MetricsRegistry()

        gauge = registry.register_gauge("test_gauge", "A test gauge")

        assert gauge is not None
        assert registry.get_metric("test_gauge") is gauge

    def test_collect(self):
        """测试采集指标"""
        registry = MetricsRegistry()
        counter = registry.register_counter("test_counter", "A test counter")

        counter.inc()
        counter.inc(domain="finance")
        counter.inc(domain="test")

        values = registry.collect()

        # Without labels: 1 value, With labels: 2 values (finance, test)
        assert len(values) >= 1
        assert any(v.name == "test_counter" for v in values)

    def test_export_prometheus(self):
        """测试导出 Prometheus 格式"""
        registry = MetricsRegistry()
        counter = registry.register_counter(
            "test_counter",
            "A test counter",
            labels=["domain"],
        )

        counter.inc(domain="test")

        output = registry.export_prometheus()

        assert "# HELP test_counter" in output
        assert "# TYPE test_counter" in output
        assert 'domain="test"' in output


class TestGlobalRegistry:
    """全局注册中心测试"""

    def test_get_registry(self):
        """测试获取全局注册中心"""
        registry = get_registry()

        assert registry is not None
        assert isinstance(registry, MetricsRegistry)

    def test_global_registry_singleton(self):
        """测试全局注册中心是单例"""
        registry1 = get_registry()
        registry2 = get_registry()

        assert registry1 is registry2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
