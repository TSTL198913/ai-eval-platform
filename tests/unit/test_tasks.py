import pytest
from celery.exceptions import Retry

from src.schemas.evaluation import DomainResponse
from src.schemas.schemas import EvaluationResult, EvaluationStatus
from src.workers.tasks import _result_to_model, eval_case_task


def test_result_to_model_maps_all_fields():
    result = EvaluationResult(
        case_id="case_x",
        status=EvaluationStatus.PASSED,
        model_name="mock-model",
        adapter_name="FinanceEvaluator",
        response=DomainResponse(is_valid=True, text="ok", score=0.95),
        latency_ms=42.5,
    )

    model = _result_to_model(result)

    assert model.case_id == "case_x"
    assert model.status == "passed"
    assert model.model_name == "mock-model"
    assert model.adapter_name == "FinanceEvaluator"
    assert model.latency_ms == 42.5
    assert model.response_data["text"] == "ok"
    assert model.response_data["score"] == 0.95


def test_eval_case_task_rejects_invalid_contract():
    with pytest.raises(Retry):
        eval_case_task.delay({"id": "bad_case"})
