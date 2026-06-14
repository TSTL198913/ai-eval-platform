from unittest.mock import MagicMock

from src.domain.evaluators.base import EvaluatorFactory
from src.schemas.evaluation import EvaluationSchema


def create_request(case_id: str, type_val: str, **payload_data) -> EvaluationSchema:
    return EvaluationSchema(
        id=case_id,
        type=type_val,
        payload=payload_data,
        metadata={},
    )


def test_registry_connectivity():
    mock_client = MagicMock()
    mock_client.chat.return_value = "语法正确，回答完整，包含机器学习关键词。"
    mock_client.config.model_name = "mock-model"

    llm_types = ["finance", "text", "code", "code_review"]
    for eval_type in llm_types:
        evaluator = EvaluatorFactory.get(eval_type, client=mock_client)
        request = create_request(
            case_id="1",
            type_val=eval_type,
            user_input="test input",
            code="def add(a,b): return a+b",
            expected_output="语法正确",
        )
        res = evaluator.evaluate(request)
        assert res is not None

    general_evaluator = EvaluatorFactory.get("general")
    general_res = general_evaluator.evaluate(
        create_request(case_id="2", type_val="general", user_input="hello")
    )
    assert general_res is not None
