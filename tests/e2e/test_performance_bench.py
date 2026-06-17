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
    if not data_path.exists():
        pytest.skip("测试数据文件不存在")
    with data_path.open("r", encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.slow
def test_performance_metrics_full_dataset(load_data, tmp_path):
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


def test_latency_distribution(mock_llm):
    latencies = []
    for _ in range(10):
        start = time.perf_counter()
        run_evaluation_service(
            {
                "id": f"latency_test_{_}",
                "type": "general",
                "payload": {"user_input": "test"},
            },
            client=mock_llm,
        )
        latencies.append((time.perf_counter() - start) * 1000)

    avg_latency = sum(latencies) / len(latencies)
    max_latency = max(latencies)
    min_latency = min(latencies)

    assert avg_latency >= 0
    assert max_latency >= min_latency
    assert all(l >= 0 for l in latencies)


def test_throughput_measurement(mock_llm):
    task_count = 20
    start_time = time.perf_counter()

    for i in range(task_count):
        run_evaluation_service(
            {
                "id": f"throughput_test_{i}",
                "type": "general",
                "payload": {"user_input": f"test {i}"},
            },
            client=mock_llm,
        )

    total_time = time.perf_counter() - start_time
    throughput = task_count / total_time

    assert throughput > 0
    assert total_time > 0


def test_concurrent_evaluation(mock_llm):
    import threading

    errors = []
    results = []

    def evaluate_task(task_id):
        try:
            result = run_evaluation_service(
                {
                    "id": f"concurrent_{task_id}",
                    "type": "general",
                    "payload": {"user_input": f"concurrent test {task_id}"},
                },
                client=mock_llm,
            )
            results.append(result)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=evaluate_task, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert len(results) == 5
    assert all(r["status"] == "success" for r in results)