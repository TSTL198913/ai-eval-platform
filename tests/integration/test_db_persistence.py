from src.services.evaluator_svc import run_evaluation_service


def test_service_success_includes_evaluation_fields(mock_llm):
    result = run_evaluation_service(
        {
            "id": "TEST_DB_001",
            "type": "finance",
            "payload": {
                "text": "1000元贷款3%一年利息",
                "expected_output": "30",
            },
        },
        client=mock_llm,
    )
    assert result["status"] == "success"
    assert result["record_id"] == "TEST_DB_001"
    assert result["evaluation_status"] == "passed"
    assert result["latency_ms"] >= 0
    assert result["data"].is_valid is True
