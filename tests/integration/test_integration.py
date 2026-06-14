from unittest.mock import MagicMock

from src.domain.evaluators.base import EvaluatorFactory
from src.engine import EvaluationEngine
from src.schemas.evaluation import EvaluationSchema, EvaluationStatus
from src.workers.tasks import eval_case_task


def test_evaluator_factory():
    evaluator = EvaluatorFactory.get("finance", client=MagicMock())
    assert evaluator is not None


def test_engine_happy_path(mock_llm):
    engine = EvaluationEngine(mock_llm)

    request = EvaluationSchema(
        id="001",
        type="finance",
        payload={
            "user_input": "请计算1000元贷款利息",
            "expected_output": "30",
        },
        metadata={},
    )

    result = engine.run(request)
    assert result.status == EvaluationStatus.PASSED
    assert result.adapter_name == "FinanceEvaluator"
    assert result.response.is_valid is True
    mock_llm.chat.assert_called_once()


def test_evaluation_pipeline_integration(mock_llm):
    case = {
        "id": "case_001",
        "type": "finance",
        "payload": {
            "user_input": "计算利息",
            "expected_output": "30",
        },
        "metadata": {"rate": 0.05},
    }

    evaluator = EvaluatorFactory.get(case["type"], client=mock_llm)
    request = EvaluationSchema(**case)
    result = evaluator.evaluate(request)

    assert result.is_valid is True
    assert result.score is not None
    mock_llm.chat.assert_called_once()


def test_eval_case_task_runs_engine(mock_llm, monkeypatch):
    from src.domain.models import llm_factory

    monkeypatch.setattr(llm_factory, "create_llm_client", lambda client=None: mock_llm)

    case_data = {
        "id": "worker_case_001",
        "type": "finance",
        "payload": {
            "user_input": "计算1000元一年期3%利息",
            "expected_output": "30",
        },
        "metadata": {},
    }

    async_result = eval_case_task.delay(case_data)
    payload = async_result.get()
    assert payload["status"] == "success"
    assert payload["evaluation_status"] == "passed"
    assert payload["case_id"] == "worker_case_001"
