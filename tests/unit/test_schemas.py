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


def test_mock_evaluation_schema_fixture(mock_evaluation_schema):
    model = mock_evaluation_schema(id="999", type="semantic")
    assert model.id == "999"
    assert model.type == "semantic"
    assert model.payload["case_id"] == "999"
