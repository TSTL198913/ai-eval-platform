from src.services.evaluator_svc import run_evaluation_service


def test_contract_error_response():
    """验证非法输入返回 CONTRACT_ERROR 且格式正确"""
    result = run_evaluation_service({"wrong_key": "nothing"})
    assert result["status"] == "error"
    assert result["code"] == "CONTRACT_ERROR"  # 修复 KeyError


def test_domain_error_response():
    """验证领域适配器缺失返回 DOMAIN_ERROR"""
    raw_data = {
        "id": "c1",
        "type": "non_existent_type",
        "payload": {"text": "test"},
    }
    result = run_evaluation_service(raw_data)
    assert result["status"] == "error"
    assert result["code"] == "DOMAIN_ERROR"  # 修复错误的 INTERNAL_ERROR 映射
