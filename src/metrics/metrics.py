"""
Prometheus 指标采集

支持:
- Counter: 计数器
- Gauge: 仪表
- Histogram: 直方图
- Summary: 摘要
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """指标类型"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class MetricValue:
    """指标值"""
    name: str
    value: float
    labels: Dict[str, str]
    timestamp: float = field(default_factory=time.time)


@dataclass
class HistogramBucket:
    """直方图桶"""
    le: float  # Less than or equal
    count: int = 0


class BaseMetric:
    """指标基类"""

    def __init__(
        self,
        name: str,
        description: str,
        labels: Optional[List[str]] = None,
    ):
        self.name = name
        self.description = description
        self.labels = labels or []
        self._values: Dict[str, float] = defaultdict(float)

    def _label_key(self, labels: Dict[str, str]) -> str:
        """生成标签键"""
        if not self.labels:
            return "_total_"
        return "|".join(f"{k}={labels.get(k, '')}" for k in self.labels)

    def _validate_labels(self, labels: Dict[str, str]) -> None:
        """验证标签"""
        for label in self.labels:
            if label not in labels:
                raise ValueError(f"Missing required label: {label}")


class Counter(BaseMetric):
    """
    计数器

    只增不减的指标，如请求总数、错误总数
    """

    def __init__(
        self,
        name: str,
        description: str,
        labels: Optional[List[str]] = None,
    ):
        super().__init__(name, description, labels)

    def inc(self, value: float = 1.0, **labels) -> None:
        """增加计数"""
        self._validate_labels(labels)
        key = self._label_key(labels)
        self._values[key] += value

    def get(self, **labels) -> float:
        """获取当前值"""
        self._validate_labels(labels)
        key = self._label_key(labels)
        return self._values[key]


class Gauge(BaseMetric):
    """
    仪表

    可以上下变化的指标，如当前连接数、内存使用
    """

    def __init__(
        self,
        name: str,
        description: str,
        labels: Optional[List[str]] = None,
    ):
        super().__init__(name, description, labels)

    def inc(self, value: float = 1.0, **labels) -> None:
        """增加"""
        self._validate_labels(labels)
        key = self._label_key(labels)
        self._values[key] += value

    def dec(self, value: float = 1.0, **labels) -> None:
        """减少"""
        self._validate_labels(labels)
        key = self._label_key(labels)
        self._values[key] -= value

    def set(self, value: float, **labels) -> None:
        """设置值"""
        self._validate_labels(labels)
        key = self._label_key(labels)
        self._values[key] = value

    def get(self, **labels) -> float:
        """获取当前值"""
        self._validate_labels(labels)
        key = self._label_key(labels)
        return self._values[key]


class Histogram(BaseMetric):
    """
    直方图

    记录值的分布，如请求延迟、响应大小
    """

    def __init__(
        self,
        name: str,
        description: str,
        buckets: Optional[List[float]] = None,
        labels: Optional[List[str]] = None,
    ):
        super().__init__(name, description, labels)
        self.buckets = buckets or [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        self._counts: Dict[str, List[int]] = defaultdict(lambda: [0] * (len(self.buckets) + 1))
        self._sums: Dict[str, float] = defaultdict(float)

    def observe(self, value: float, **labels) -> None:
        """记录观测值"""
        self._validate_labels(labels)
        key = self._label_key(labels)

        self._sums[key] += value
        for i, bound in enumerate(self.buckets):
            if value <= bound:
                self._counts[key][i] += 1
        self._counts[key][-1] += 1  # +Inf bucket

    def get_stats(self, **labels) -> Dict[str, Any]:
        """获取统计信息"""
        self._validate_labels(labels)
        key = self._label_key(labels)

        total = self._counts[key][-1]
        return {
            "count": total,
            "sum": self._sums[key],
            "mean": self._sums[key] / total if total > 0 else 0,
            "buckets": {
                f"le_{bound}": self._counts[key][i]
                for i, bound in enumerate(self.buckets)
            },
        }


class Summary(BaseMetric):
    """
    摘要

    记录分位数，如 P50、P90、P99
    """

    def __init__(
        self,
        name: str,
        description: str,
        quantiles: Optional[List[float]] = None,
        labels: Optional[List[str]] = None,
    ):
        super().__init__(name, description, labels)
        self.quantiles = quantiles or [0.5, 0.9, 0.99]
        self._values: Dict[str, List[float]] = defaultdict(list)

    def observe(self, value: float, **labels) -> None:
        """记录观测值"""
        self._validate_labels(labels)
        key = self._label_key(labels)
        self._values[key].append(value)

    def get_quantiles(self, **labels) -> Dict[str, float]:
        """获取分位数"""
        self._validate_labels(labels)
        key = self._label_key(labels)

        values = sorted(self._values[key])
        if not values:
            return {f"q{q}": 0.0 for q in self.quantiles}

        return {
            f"q{q}": values[int(len(values) * q)] if int(len(values) * q) < len(values) else values[-1]
            for q in self.quantiles
        }


class MetricsRegistry:
    """
    指标注册中心

    管理所有指标，提供统一采集和导出
    """

    def __init__(self):
        self._metrics: Dict[str, BaseMetric] = {}
        self._counters: Dict[str, Counter] = {}
        self._gauges: Dict[str, Gauge] = {}
        self._histograms: Dict[str, Histogram] = {}
        self._summaries: Dict[str, Summary] = {}

    def register_counter(
        self,
        name: str,
        description: str,
        labels: Optional[List[str]] = None,
    ) -> Counter:
        """注册计数器"""
        counter = Counter(name, description, labels)
        self._metrics[name] = counter
        self._counters[name] = counter
        return counter

    def register_gauge(
        self,
        name: str,
        description: str,
        labels: Optional[List[str]] = None,
    ) -> Gauge:
        """注册仪表"""
        gauge = Gauge(name, description, labels)
        self._metrics[name] = gauge
        self._gauges[name] = gauge
        return gauge

    def register_histogram(
        self,
        name: str,
        description: str,
        buckets: Optional[List[float]] = None,
        labels: Optional[List[str]] = None,
    ) -> Histogram:
        """注册直方图"""
        histogram = Histogram(name, description, buckets, labels)
        self._metrics[name] = histogram
        self._histograms[name] = histogram
        return histogram

    def register_summary(
        self,
        name: str,
        description: str,
        quantiles: Optional[List[float]] = None,
        labels: Optional[List[str]] = None,
    ) -> Summary:
        """注册摘要"""
        summary = Summary(name, description, quantiles, labels)
        self._metrics[name] = summary
        self._summaries[name] = summary
        return summary

    def get_metric(self, name: str) -> Optional[BaseMetric]:
        """获取指标"""
        return self._metrics.get(name)

    def collect(self) -> List[MetricValue]:
        """采集所有指标"""
        values = []
        for metric in self._metrics.values():
            if isinstance(metric, (Counter, Gauge)):
                for key, value in metric._values.items():
                    labels = self._parse_label_key(key, metric.labels)
                    values.append(MetricValue(
                        name=metric.name,
                        value=value,
                        labels=labels,
                    ))
            elif isinstance(metric, Histogram):
                for key in metric._counts:
                    stats = metric.get_stats(**self._parse_label_key(key, metric.labels))
                    labels = self._parse_label_key(key, metric.labels)
                    values.append(MetricValue(
                        name=f"{metric.name}_count",
                        value=stats["count"],
                        labels=labels,
                    ))
                    values.append(MetricValue(
                        name=f"{metric.name}_sum",
                        value=stats["sum"],
                        labels=labels,
                    ))
        return values

    @staticmethod
    def _parse_label_key(key: str, label_names: List[str]) -> Dict[str, str]:
        """解析标签键"""
        if key == "_total_" or not label_names:
            return {}
        result = {}
        parts = key.split("|")
        for i, name in enumerate(label_names):
            if i < len(parts):
                result[name] = parts[i].split("=")[1] if "=" in parts[i] else parts[i]
        return result

    def export_prometheus(self) -> str:
        """导出 Prometheus 格式"""
        lines = []
        for metric in self._metrics.values():
            metric_type = self._get_metric_type(metric)
            lines.append(f"# HELP {metric.name} {metric.description}")
            lines.append(f"# TYPE {metric.name} {metric_type}")

            if isinstance(metric, Counter):
                for key, value in metric._values.items():
                    labels = self._format_labels(self._parse_label_key(key, metric.labels))
                    lines.append(f"{metric.name}{labels} {value}")

            elif isinstance(metric, Gauge):
                for key, value in metric._values.items():
                    labels = self._format_labels(self._parse_label_key(key, metric.labels))
                    lines.append(f"{metric.name}{labels} {value}")

            elif isinstance(metric, Histogram):
                for key in metric._counts:
                    stats = metric.get_stats(**self._parse_label_key(key, metric.labels))
                    labels = self._format_labels(self._parse_label_key(key, metric.labels))
                    lines.append(f"{metric.name}_count{labels} {stats['count']}")
                    lines.append(f"{metric.name}_sum{labels} {stats['sum']}")

        return "\n".join(lines)

    @staticmethod
    def _get_metric_type(metric: BaseMetric) -> str:
        """获取指标类型字符串"""
        if isinstance(metric, Counter):
            return "counter"
        elif isinstance(metric, Gauge):
            return "gauge"
        elif isinstance(metric, Histogram):
            return "histogram"
        elif isinstance(metric, Summary):
            return "summary"
        return "untyped"

    @staticmethod
    def _format_labels(labels: Dict[str, str]) -> str:
        """格式化标签"""
        if not labels:
            return ""
        return "{" + ",".join(f'{k}="{v}"' for k, v in labels.items()) + "}"


# 全局注册中心
_global_registry = MetricsRegistry()


def get_registry() -> MetricsRegistry:
    """获取全局注册中心"""
    return _global_registry


# 预定义指标
def create_standard_metrics() -> None:
    """创建标准指标"""
    registry = get_registry()

    # 任务相关
    registry.register_counter(
        "eval_tasks_total",
        "Total number of evaluation tasks",
        ["domain", "status"],
    )

    registry.register_histogram(
        "eval_task_duration_seconds",
        "Evaluation task duration in seconds",
        ["domain"],
    )

    registry.register_counter(
        "eval_task_errors_total",
        "Total number of evaluation errors",
        ["domain", "error_type"],
    )

    # LLM 相关
    registry.register_counter(
        "llm_requests_total",
        "Total number of LLM requests",
        ["model", "status"],
    )

    registry.register_histogram(
        "llm_request_duration_seconds",
        "LLM request duration in seconds",
        ["model"],
    )

    # 队列相关
    registry.register_gauge(
        "queue_size",
        "Current queue size",
        ["queue_name"],
    )

    registry.register_counter(
        "queue_messages_total",
        "Total number of queue messages",
        ["queue_name", "direction"],
    )

    # Worker 相关
    registry.register_gauge(
        "worker_active_tasks",
        "Number of active tasks per worker",
        ["worker_id"],
    )


# 初始化标准指标
create_standard_metrics()
