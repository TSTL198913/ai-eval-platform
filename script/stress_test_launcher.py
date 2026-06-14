import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.infra.analytics.benchmark_report import (  # noqa: E402
    build_benchmark_report,
    format_benchmark_summary,
    save_benchmark_report,
)
from src.infra.db.models import EvaluationResultModel  # noqa: E402
from src.infra.db.session import SessionLocal  # noqa: E402
from src.workers.tasks import eval_case_task  # noqa: E402

TOTAL_TASKS = int(os.getenv("STRESS_TOTAL_TASKS", "100"))
REPORT_PATH = os.getenv(
    "STRESS_REPORT_PATH",
    str(PROJECT_ROOT / "reports" / "stress_report.json"),
)
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))


SAMPLE_CASES = [
    {
        "type": "finance",
        "payload": {
            "user_input": "1000元贷款年化3%一年利息多少",
            "expected_output": "30",
        },
    },
    {
        "type": "text",
        "payload": {
            "user_input": "解释什么是机器学习",
            "expected_output": "机器学习",
        },
    },
    {
        "type": "code",
        "payload": {
            "code": "def add(a, b):\n    return a + b",
            "expected_output": "语法正确",
        },
    },
]


def get_db_count() -> int:
    db = SessionLocal()
    try:
        return db.query(EvaluationResultModel).count()
    finally:
        db.close()


def submit_tasks(total_tasks: int):
    latencies = []
    errors = {}
    start = time.perf_counter()

    for i in range(1, total_tasks + 1):
        sample = SAMPLE_CASES[(i - 1) % len(SAMPLE_CASES)]
        case_data = {
            "id": f"stress_{i}_{int(time.time())}",
            "type": sample["type"],
            "payload": sample["payload"],
            "metadata": {"batch": "stress_p1"},
        }

        task_start = time.perf_counter()
        try:
            eval_case_task.delay(case_data)
        except Exception as exc:
            code = type(exc).__name__
            errors[code] = errors.get(code, 0) + 1
        latencies.append((time.perf_counter() - task_start) * 1000)

        if i % max(total_tasks // 10, 1) == 0:
            print(f"  已提交 {i}/{total_tasks}")

    submit_ms = (time.perf_counter() - start) * 1000
    return latencies, errors, submit_ms


def wait_for_queue_drain(timeout_sec: int = 120):
    try:
        import redis

        client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, protocol=2)
        start = time.time()
        while time.time() - start < timeout_sec:
            pending = client.llen("celery")
            if pending == 0:
                return True, time.time() - start
            print(f"  队列剩余 {pending} 条，等待消费...")
            time.sleep(2)
        return False, timeout_sec
    except Exception as exc:
        print(f"  Redis 不可用，跳过队列监控: {exc}")
        return None, 0.0


def main():
    print("=" * 70)
    print(f"[{datetime.now()}] 分布式压测启动，目标任务数: {TOTAL_TASKS}")
    print("=" * 70)

    base_count = get_db_count()
    latencies, submit_errors, submit_ms = submit_tasks(TOTAL_TASKS)

    drained, drain_sec = wait_for_queue_drain()
    time.sleep(2)

    current_count = get_db_count()
    actual_new = current_count - base_count

    report = build_benchmark_report(
        latencies_ms=latencies,
        success_count=TOTAL_TASKS - sum(submit_errors.values()),
        total_cases=TOTAL_TASKS,
        error_summary=submit_errors,
    )
    report_dict = report.to_dict()
    report_dict.update(
        {
            "submit_total_ms": submit_ms,
            "queue_drained": drained,
            "queue_drain_sec": drain_sec,
            "db_baseline_count": base_count,
            "db_new_records": actual_new,
            "db_reconciliation_passed": actual_new >= TOTAL_TASKS,
        }
    )

    output = save_benchmark_report(report, REPORT_PATH)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(report_dict, f, ensure_ascii=False, indent=2)

    print(format_benchmark_summary(report))
    print(f"DB 新增记录: {actual_new} / {TOTAL_TASKS}")
    print(f"报告已写入: {output}")


if __name__ == "__main__":
    main()
