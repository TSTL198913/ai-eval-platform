import pytest

from src.schemas.evaluation import EvaluationSchema


def test_eval_schema_creation():
    data = {
        "id": "123",
        "type": "text",
        "payload": {"case_id": "TEST_001", "domain": "Finance"},
        "metadata": {"config": "val"},
    }
    model = EvaluationSchema(**data)

    assert model.id == "123"
    assert model.type == "text"
    assert model.payload["case_id"] == "TEST_001"
    assert model.metadata["config"] == "val"


def test_eval_schema_rejects_missing_required_fields():
    with pytest.raises(Exception):
        EvaluationSchema(id="only_id")


def test_eval_schema_default_metadata():
    data = {
        "id": "123",
        "type": "text",
        "payload": {"case_id": "TEST_001"},
    }
    model = EvaluationSchema(**data)

    assert model.metadata is None
