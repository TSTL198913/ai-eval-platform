"""结果转换测试"""
from src.schemas.evaluation import DomainResponse
from src.schemas.schemas import EvaluationResult, EvaluationStatus
from src.workers.tasks import _result_to_model


class MockEvaluationResultModel:
    """Mock 模型类"""
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestResultToModel:
    """结果转换测试"""

    def test_result_to_model(self):
        """测试结果转换为模型"""
        result = EvaluationResult(
            case_id="c1",
            model_name="gpt-4",
            adapter_name="default",
            status=EvaluationStatus.PASSED,
            latency_ms=100.0,
            response=DomainResponse(is_valid=True),
        )

        model = _result_to_model(result)

        assert hasattr(model, "case_id")
        assert model.case_id == "c1"
        assert model.model_name == "gpt-4"
        assert model.status == "passed"

    def test_result_to_model_with_response(self):
        """测试带响应的结果转换"""
        result = EvaluationResult(
            case_id="c1",
            model_name="gpt-4",
            adapter_name="default",
            status=EvaluationStatus.PASSED,
            latency_ms=100.0,
            response=DomainResponse(is_valid=True, score=1.0),
        )

        model = _result_to_model(result)

        assert hasattr(model, "response_data")
        assert model.response_data["is_valid"] is True
        assert model.response_data["score"] == 1.0

    def test_result_to_model_with_error(self):
        """测试带错误的结果转换"""
        result = EvaluationResult(
            case_id="c1",
            model_name="gpt-4",
            adapter_name="default",
            status=EvaluationStatus.ERROR,
            latency_ms=100.0,
            response=DomainResponse(is_valid=False, error="Test error"),
        )

        model = _result_to_model(result)

        assert hasattr(model, "response_data")
        assert model.response_data["error"] == "Test error"