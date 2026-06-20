from src.api.common import (
    error_response,
    success_response,
    validate_dataset_name,
    validate_evaluator_name,
)


class TestValidateEvaluatorName:
    def test_valid_name(self):
        assert validate_evaluator_name("qa") is True
        assert validate_evaluator_name("code-review") is True
        assert validate_evaluator_name("test_123") is True
        assert validate_evaluator_name("my-evaluator") is True

    def test_invalid_name(self):
        assert validate_evaluator_name("") is False
        assert validate_evaluator_name(None) is False
        assert validate_evaluator_name(" ") is False
        assert validate_evaluator_name("/") is False
        assert validate_evaluator_name("eval/name") is False
        assert validate_evaluator_name("eval name") is False
        assert validate_evaluator_name('eval"name') is False

    def test_sql_injection_attempt(self):
        assert validate_evaluator_name("eval'; DROP TABLE") is False
        assert validate_evaluator_name("1'; SELECT * FROM") is False


class TestValidateDatasetName:
    def test_valid_name(self):
        assert validate_dataset_name("gsm8k") is True
        assert validate_dataset_name("my-dataset") is True
        assert validate_dataset_name("dataset_2024") is True

    def test_invalid_name(self):
        assert validate_dataset_name("") is False
        assert validate_dataset_name(None) is False
        assert validate_dataset_name(" ") is False
        assert validate_dataset_name("data/set") is False


class TestSuccessResponse:
    def test_with_data(self):
        result = success_response(data={"score": 0.8})
        assert result == {"code": 0, "message": "success", "data": {"score": 0.8}}

    def test_with_custom_message(self):
        result = success_response(message="操作成功")
        assert result["message"] == "操作成功"

    def test_empty_data(self):
        result = success_response()
        assert result["data"] is None


class TestErrorResponse:
    def test_error_response(self):
        result = error_response(code=400, message="参数错误")
        assert result == {"code": 400, "message": "参数错误", "data": None}

    def test_different_error_codes(self):
        result = error_response(code=500, message="服务器错误")
        assert result["code"] == 500
