"""数据契约：EvaluationSchema 与生产模拟数据集一致性。"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.domain.evaluators import EVALUATOR_REGISTRY
from src.schemas.evaluation import EvaluationSchema

pytestmark = pytest.mark.contract

PROD_CASES_PATH = Path("tests/prod_simulated_cases.json")


def test_evaluation_schema_required_fields():
    with pytest.raises(ValidationError):
        EvaluationSchema(id="only_id")

    case = EvaluationSchema(
        id="c1",
        type="finance",
        payload={"user_input": "test"},
    )
    assert case.id == "c1"
    assert case.type == "finance"
    assert case.metadata is None


def test_evaluation_schema_is_frozen():
    case = EvaluationSchema(id="c1", type="text", payload={"x": 1})
    with pytest.raises(Exception):
        case.id = "changed"


def test_prod_simulated_cases_match_schema():
    cases = json.loads(PROD_CASES_PATH.read_text(encoding="utf-8"))
    assert len(cases) > 0

    for case in cases:
        payload = case.get("payload")
        if isinstance(payload, str):
            payload = json.loads(payload)
        normalized = {
            "id": case["id"],
            "type": case["type"],
            "payload": payload,
            "metadata": case.get("metadata", {}),
        }
        model = EvaluationSchema(**normalized)
        assert model.id == case["id"]
        assert model.type in EVALUATOR_REGISTRY
