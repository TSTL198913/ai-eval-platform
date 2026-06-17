import pytest

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
    assert "latency_ms" in result
    assert result["latency_ms"] >= 0


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


def test_pipeline_empty_payload(mock_llm):
    raw_data = {
        "id": "empty_payload_case",
        "type": "general",
        "payload": {},
    }
    result = run_evaluation_service(raw_data, client=mock_llm)
    assert result["status"] == "success"


def test_pipeline_empty_id(mock_llm):
    raw_data = {
        "id": "",
        "type": "general",
        "payload": {"user_input": "test"},
    }
    result = run_evaluation_service(raw_data, client=mock_llm)
    assert result["status"] == "success"
    assert result["record_id"] == ""


def test_pipeline_missing_id(mock_llm):
    raw_data = {
        "type": "general",
        "payload": {"user_input": "test"},
    }
    result = run_evaluation_service(raw_data, client=mock_llm)
    assert result["status"] == "error"
    assert result["code"] == "CONTRACT_ERROR"


def test_pipeline_missing_type():
    raw_data = {
        "id": "missing_type_case",
        "payload": {"user_input": "test"},
    }
    result = run_evaluation_service(raw_data)
    assert result["status"] == "error"


def test_pipeline_invalid_payload_type():
    raw_data = {
        "id": "invalid_payload_case",
        "type": "general",
        "payload": "not_a_dict",
    }
    result = run_evaluation_service(raw_data)
    assert result["status"] == "error"
    assert result["code"] == "CONTRACT_ERROR"


def test_pipeline_large_payload(mock_llm):
    raw_data = {
        "id": "large_payload_case",
        "type": "general",
        "payload": {
            "user_input": "x" * 10000,
            "expected_output": "x" * 1000,
        },
    }
    result = run_evaluation_service(raw_data, client=mock_llm)
    assert result["status"] == "success"


def test_pipeline_special_characters_in_id(mock_llm):
    raw_data = {
        "id": "case:with/special characters!@#$%^&*()",
        "type": "general",
        "payload": {"user_input": "test"},
    }
    result = run_evaluation_service(raw_data, client=mock_llm)
    assert result["status"] == "success"
    assert result["record_id"] == "case:with/special characters!@#$%^&*()"


def test_pipeline_unicode_payload(mock_llm):
    raw_data = {
        "id": "unicode_case",
        "type": "general",
        "payload": {
            "user_input": "测试中文输入",
            "expected_output": "测试中文输出",
        },
    }
    result = run_evaluation_service(raw_data, client=mock_llm)
    assert result["status"] == "success"