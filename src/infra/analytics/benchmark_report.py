import json
import statistics
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = int(len(sorted_values) * pct)
    index = min(index, len(sorted_values) - 1)
    return sorted_values[index]


@dataclass
class BenchmarkReport:
    total_cases: int
    success_count: int
    success_rate: float
    total_time_ms: float
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    tps: float
    error_summary: Dict[str, int] = field(default_factory=dict)
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_benchmark_report(
    latencies_ms: List[float],
    success_count: int,
    total_cases: int,
    error_summary: Optional[Dict[str, int]] = None,
) -> BenchmarkReport:
    total_time_ms = sum(latencies_ms)
    total_cases = max(total_cases, 1)
    success_rate = success_count / total_cases
    avg_latency = statistics.mean(latencies_ms) if latencies_ms else 0.0
    tps = (total_cases / (total_time_ms / 1000)) if total_time_ms > 0 else 0.0

    return BenchmarkReport(
        total_cases=total_cases,
        success_count=success_count,
        success_rate=success_rate,
        total_time_ms=total_time_ms,
        avg_latency_ms=avg_latency,
        p50_latency_ms=percentile(latencies_ms, 0.50),
        p95_latency_ms=percentile(latencies_ms, 0.95),
        p99_latency_ms=percentile(latencies_ms, 0.99),
        tps=tps,
        error_summary=error_summary or {},
    )


def save_benchmark_report(report: BenchmarkReport, output_path: str) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return str(path)


def format_benchmark_summary(report: BenchmarkReport) -> str:
    lines = [
        "=" * 48,
        "Benchmark Report",
        f"Generated At : {report.generated_at}",
        f"Total Cases  : {report.total_cases}",
        f"Success Rate : {report.success_rate:.2%}",
        f"Avg Latency  : {report.avg_latency_ms:.2f} ms",
        f"P50 Latency  : {report.p50_latency_ms:.2f} ms",
        f"P95 Latency  : {report.p95_latency_ms:.2f} ms",
        f"P99 Latency  : {report.p99_latency_ms:.2f} ms",
        f"TPS          : {report.tps:.2f}",
        f"Error Summary: {report.error_summary}",
        "=" * 48,
    ]
    return "\n".join(lines)
