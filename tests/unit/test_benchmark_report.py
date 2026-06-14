from src.infra.analytics.benchmark_report import (
    build_benchmark_report,
    format_benchmark_summary,
    percentile,
    save_benchmark_report,
)


def test_percentile_empty_list():
    assert percentile([], 0.95) == 0.0


def test_build_benchmark_report_metrics():
    latencies = [10.0, 20.0, 30.0, 40.0, 100.0]
    report = build_benchmark_report(
        latencies_ms=latencies,
        success_count=4,
        total_cases=5,
        error_summary={"DOMAIN_ERROR": 1},
    )

    assert report.total_cases == 5
    assert report.success_count == 4
    assert report.success_rate == 0.8
    assert report.p50_latency_ms == 30.0
    assert report.p95_latency_ms == 100.0
    assert report.error_summary["DOMAIN_ERROR"] == 1


def test_save_benchmark_report_writes_json(tmp_path):
    report = build_benchmark_report(
        latencies_ms=[5.0, 15.0],
        success_count=2,
        total_cases=2,
    )
    output = save_benchmark_report(report, str(tmp_path / "bench.json"))
    content = (tmp_path / "bench.json").read_text(encoding="utf-8")
    assert "success_rate" in content
    assert output.endswith("bench.json")


def test_format_benchmark_summary_contains_key_fields():
    report = build_benchmark_report([1.0, 2.0], 2, 2)
    summary = format_benchmark_summary(report)
    assert "Success Rate" in summary
    assert "P95 Latency" in summary
