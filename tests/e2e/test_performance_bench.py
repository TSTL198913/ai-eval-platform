import json
import time
from pathlib import Path

import pytest

from src.infra.analytics.benchmark_report import build_benchmark_report
from src.services.evaluator_svc import run_evaluation_service

SAMPLE_CASES = [
    {
        "id": "bench_finance",
        "type": "finance",
        "payload": {"user_input": "1000元3%一年利息", "expected_output": "30"},
    },
    {
        "id": "bench_text",
        "type": "text",
        "payload": {
            "user_input": "什么是机器学习",
            "expected_output": "机器学习是人工智能的重要分支",
        },
    },
    {
        "id": "bench_code",
        "type": "code",
        "payload": {
            "code": "def add(a, b):\n    return a + b",
            "expected_output": "语法正确",
        },
    },
]


@pytest.mark.parametrize("case", SAMPLE_CASES, ids=[c["id"] for c in SAMPLE_CASES])
def test_sample_case_evaluation_success(case, mock_llm):
    if case["type"] == "text":
        mock_llm.chat.return_value = "机器学习是人工智能的重要分支，用于从数据中学习。"
    elif case["type"] == "code":
        mock_llm.chat.return_value = "语法正确，函数实现简洁，无明显问题。"

    result = run_evaluation_service(case, client=mock_llm)
    assert result["status"] == "success"
    assert result["evaluation_status"] == "passed"
    assert result["latency_ms"] >= 0


def test_benchmark_report_from_sample_cases(mock_llm, tmp_path):
    latencies = []
    success = 0

    for case in SAMPLE_CASES:
        start = time.perf_counter()
        result = run_evaluation_service(case, client=mock_llm)
        latencies.append((time.perf_counter() - start) * 1000)
        if result["status"] == "success":
            success += 1

    report = build_benchmark_report(latencies, success, len(SAMPLE_CASES))
    assert report.success_rate == 1.0
    assert report.total_cases == 3

    out = tmp_path / "sample_bench.json"
    out.write_text(json.dumps(report.to_dict()), encoding="utf-8")
    assert out.exists()


@pytest.fixture
def load_data():
    data_path = Path("tests/prod_simulated_cases.json")
    with data_path.open("r", encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.slow
def test_performance_metrics_full_dataset(load_data, tmp_path):
    """全量 prod 数据集压测，仅本地/CI nightly 执行。"""
    latencies = []
    success_count = 0
    processed = 0
    error_summary = {}

    for case in load_data:
        payload = case.get("payload")
        if isinstance(payload, str):
            try:
                case["payload"] = json.loads(payload)
            except json.JSONDecodeError:
                continue

        normalized_payload = dict(case.get("payload") or {})
        if "user_input" not in normalized_payload and "text" in normalized_payload:
            normalized_payload.setdefault("user_input", normalized_payload["text"])
        case["payload"] = normalized_payload

        start = time.perf_counter()
        result = run_evaluation_service(case)
        latencies.append((time.perf_counter() - start) * 1000)
        processed += 1
        if result.get("status") == "success":
            success_count += 1
        else:
            code = result.get("code", "UNKNOWN_ERROR")
            error_summary[code] = error_summary.get(code, 0) + 1

    report = build_benchmark_report(
        latencies_ms=latencies,
        success_count=success_count,
        total_cases=processed,
        error_summary=error_summary,
    )
    report_path = tmp_path / "performance_report.json"
    report_path.write_text(json.dumps(report.to_dict()), encoding="utf-8")

    assert processed > 0
    assert report.success_rate == 1.0, error_summary
