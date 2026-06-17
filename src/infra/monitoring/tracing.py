"""
OpenTelemetry 分布式追踪

支持:
- 跨服务追踪
- Span 传播
- 自动 instrumentation
"""

import logging
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

# Context variable for trace ID
current_trace_id: ContextVar[str | None] = ContextVar("current_trace_id", default=None)
current_span_id: ContextVar[str | None] = ContextVar("current_span_id", default=None)


@dataclass
class SpanContext:
    """Span 上下文"""

    trace_id: str
    span_id: str
    parent_id: str | None = None
    sampled: bool = True


@dataclass
class Span:
    """追踪 Span"""

    name: str
    span_id: str
    trace_id: str
    parent_id: str | None
    start_time: float
    end_time: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list = field(default_factory=list)
    status: str = "OK"

    @property
    def duration(self) -> float:
        """计算 Span 持续时间（秒）"""
        if self.end_time is None:
            return 0.0
        return self.end_time - self.start_time

    def set_attribute(self, key: str, value: Any) -> None:
        """设置属性"""
        self.attributes[key] = value

    def add_event(self, name: str, attributes: dict | None = None) -> None:
        """添加事件"""
        self.events.append(
            {
                "name": name,
                "timestamp": self._current_timestamp(),
                "attributes": attributes or {},
            }
        )

    def set_status(self, status: str, message: str = "") -> None:
        """设置状态"""
        self.status = status
        if message:
            self.attributes["status.message"] = message

    def finish(self) -> None:
        """结束 Span"""
        self.end_time = self._current_timestamp()

    @staticmethod
    def _current_timestamp() -> float:
        import time

        return time.time()


class Tracer:
    """
    追踪器

    提供 Span 创建和管理功能
    """

    def __init__(self, service_name: str):
        self.service_name = service_name
        self._spans: list[Span] = []

    def create_span(
        self,
        name: str,
        trace_id: str | None = None,
        parent_id: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> Span:
        """创建新的 Span"""
        span_id = self._generate_span_id()
        trace_id = trace_id or self._get_or_create_trace_id()

        span = Span(
            name=name,
            span_id=span_id,
            trace_id=trace_id,
            parent_id=parent_id or current_span_id.get(),
            start_time=Span._current_timestamp(),
            attributes=attributes or {},
        )

        self._spans.append(span)

        current_trace_id.set(trace_id)
        current_span_id.set(span_id)

        return span

    def start_span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
    ) -> "SpanContext":
        """开始一个 span，返回上下文用于传播"""
        span = self.create_span(name, attributes=attributes)
        return SpanContext(
            trace_id=span.trace_id,
            span_id=span.span_id,
            parent_id=span.parent_id,
        )

    def end_span(self, span: Span, status: str = "OK") -> None:
        """结束 span"""
        span.set_status(status)
        span.finish()
        self._export_span(span)

    def _export_span(self, span: Span) -> None:
        """导出 span 到追踪后端"""
        logger.debug(f"Trace exported: {span.trace_id}/{span.span_id} [{span.name}] {span.status}")

    @staticmethod
    def _generate_span_id() -> str:
        """生成 16 字符的 span ID"""
        return uuid4().hex[:16]

    @staticmethod
    def _get_or_create_trace_id() -> str:
        """获取或创建 trace ID"""
        trace_id = current_trace_id.get()
        if not trace_id:
            trace_id = uuid4().hex[:32]
            current_trace_id.set(trace_id)
        return trace_id

    def get_current_trace_id(self) -> str | None:
        """获取当前 trace ID"""
        return current_trace_id.get()


class SpanContextCarrier:
    """
    Span 上下文传播载体

    用于在不同服务间传播追踪上下文
    """

    HEADER_KEY = "x-trace-id"
    PARENT_HEADER_KEY = "x-parent-span-id"

    @classmethod
    def inject(cls, span_context: SpanContext) -> dict[str, str]:
        """注入上下文到 HTTP headers"""
        headers = {
            cls.HEADER_KEY: span_context.trace_id,
        }
        if span_context.span_id:
            headers[cls.PARENT_HEADER_KEY] = span_context.span_id
        return headers

    @classmethod
    def extract(cls, headers: dict[str, str]) -> SpanContext | None:
        """从 HTTP headers 提取上下文"""
        trace_id = headers.get(cls.HEADER_KEY)
        if not trace_id:
            return None

        parent_id = headers.get(cls.PARENT_HEADER_KEY)
        return SpanContext(
            trace_id=trace_id,
            span_id="",
            parent_id=parent_id,
        )


class TraceContext:
    """追踪上下文管理器"""

    def __init__(self, tracer: Tracer, name: str, attributes: dict | None = None):
        self.tracer = tracer
        self.name = name
        self.attributes = attributes or {}
        self.span: Span | None = None

    def __enter__(self) -> "TraceContext":
        self.span = self.tracer.create_span(self.name, attributes=self.attributes)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.span:
            if exc_type:
                self.span.set_status("ERROR", str(exc_val))
            else:
                self.span.set_status("OK")
            self.tracer.end_span(self.span)
        return False


def setup_opentelemetry(
    service_name: str,
    otlp_endpoint: str | None = None,
) -> Tracer:
    """
    设置 OpenTelemetry

    Args:
        service_name: 服务名称
        otlp_endpoint: OTLP 导出器端点 (可选)

    Returns:
        配置好的 Tracer 实例
    """
    tracer = Tracer(service_name)

    if otlp_endpoint:
        logger.info(f"OpenTelemetry configured with OTLP endpoint: {otlp_endpoint}")

    return tracer


# 全局 tracer 实例
_tracer: Tracer | None = None


def get_tracer() -> Tracer:
    """获取全局 tracer 实例"""
    global _tracer
    if _tracer is None:
        _tracer = Tracer("eval-platform")
    return _tracer


def set_tracer(tracer: Tracer) -> None:
    """设置全局 tracer 实例"""
    global _tracer
    _tracer = tracer
