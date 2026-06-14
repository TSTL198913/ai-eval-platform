from src.workers.tasks import eval_case_task


def test_task_crash_and_recovery():
    result = eval_case_task.delay(
        {
            "id": "TEST_001",
            "type": "general",
            "payload": {"user_input": "recovery test"},
        }
    )
    assert result is not None
    payload = result.get()
    assert payload["status"] == "success"
