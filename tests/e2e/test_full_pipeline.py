from src.services.evaluator_svc import run_evaluation_service


def test_full_pipeline_success(mock_llm):
    raw_data = {
        "id": "case_101",
        "type": "finance",
        "payload": {
            "user_input": "1000元贷款3%一年利息",
            "expected_output": "30",
        },
    }
    result = run_evaluation_service(raw_data, client=mock_llm)

    assert result["status"] == "success"
    assert result["record_id"] == "case_101"
    assert result["evaluation_status"] == "passed"
    assert result["data"].score >= 0.8


def test_pipeline_contract_error():
    result = run_evaluation_service({"wrong_key": "nothing"})
    assert result["status"] == "error"
    assert result["code"] == "CONTRACT_ERROR"
    assert "message" in result


def test_pipeline_domain_error():
    raw_data = {
        "id": "case_102",
        "type": "non_existent_type",
        "payload": {"data": "test"},
    }
    result = run_evaluation_service(raw_data)
    assert result["status"] == "error"
    assert result["code"] == "DOMAIN_ERROR"


def test_pipeline_legacy_format_without_payload_key(mock_llm):
    legacy = {
        "id": "legacy_case",
        "type": "general",
        "user_input": "legacy hello",
    }
    result = run_evaluation_service(legacy, client=mock_llm)
    assert result["status"] == "success"
    assert result["record_id"] == "legacy_case"
