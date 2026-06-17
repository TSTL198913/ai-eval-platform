import time
from datetime import datetime

import pytest

from src.schemas.evaluation import EvaluationSchema
from src.workers.tasks import eval_case_task, buffer_service


@pytest.fixture(autouse=True)
def clean_buffer():
    buffer_service.buffer.clear()
    yield


def test_stress_test_single_task(mock_llm):
    mock_schema_obj = EvaluationSchema(
        id="STRESS_TEST_001",
        type="text",
        payload={
            "case_id": "c_0",
            "user_input": "高并发测试输入",
            "domain": "text",
        },
        metadata={"batch": "stress_test"},
    )

    eval_case_task.delay(mock_schema_obj.model_dump())

    assert len(buffer_service.buffer) == 1


def test_stress_test_multiple_tasks(mock_llm):
    task_count = 10

    for i in range(task_count):
        eval_type = "text" if i % 2 == 0 else "code"
        mock_schema_obj = EvaluationSchema(
            id=f"STRESS_TEST_{i}",
            type=eval_type,
            payload={
                "case_id": f"c_{i}",
                "user_input": f"高并发测试输入 - 编号 {i}",
                "domain": eval_type,
            },
            metadata={"batch": "stress_test"},
        )
        eval_case_task.delay(mock_schema_obj.model_dump())

    assert len(buffer_service.buffer) == task_count


def test_stress_test_task_submit_performance(mock_llm):
    task_count = 20
    start_time = time.time()

    for i in range(task_count):
        mock_schema_obj = EvaluationSchema(
            id=f"PERF_TEST_{i}_{int(time.time())}",
            type="general",
            payload={
                "case_id": f"c_{i}",
                "user_input": f"性能测试输入 - 编号 {i}",
                "domain": "general",
            },
            metadata={"batch": "performance_test"},
        )
        eval_case_task.delay(mock_schema_obj.model_dump())

    total_duration = time.time() - start_time
    tps = task_count / total_duration

    assert tps > 0
    assert total_duration > 0


def test_stress_test_mixed_domain_tasks(mock_llm):
    domains = ["text", "code", "finance", "general", "qa"]
    tasks_per_domain = 3

    for domain in domains:
        for i in range(tasks_per_domain):
            mock_schema_obj = EvaluationSchema(
                id=f"MIXED_{domain}_{i}",
                type=domain,
                payload={
                    "case_id": f"mixed_{domain}_{i}",
                    "user_input": f"{domain} domain test {i}",
                    "domain": domain,
                },
                metadata={"batch": "mixed_domain_test"},
            )
            eval_case_task.delay(mock_schema_obj.model_dump())

    assert len(buffer_service.buffer) == len(domains) * tasks_per_domain


def test_stress_test_empty_payload(mock_llm):
    mock_schema_obj = EvaluationSchema(
        id="EMPTY_PAYLOAD_TEST",
        type="general",
        payload={},
        metadata={"batch": "empty_payload_test"},
    )

    eval_case_task.delay(mock_schema_obj.model_dump())

    assert len(buffer_service.buffer) == 1


def test_stress_test_large_payload(mock_llm):
    mock_schema_obj = EvaluationSchema(
        id="LARGE_PAYLOAD_TEST",
        type="general",
        payload={
            "case_id": "large_payload_case",
            "user_input": "x" * 5000,
            "domain": "general",
        },
        metadata={"batch": "large_payload_test"},
    )

    eval_case_task.delay(mock_schema_obj.model_dump())

    assert len(buffer_service.buffer) == 1