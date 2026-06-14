from src.infra.db.repository import EvaluationRepository
from src.schemas.evaluation import DomainResponse
from src.schemas.schemas import EvaluationResult, EvaluationStatus


def test_save_evaluation_result_persists_to_db():
    repo = EvaluationRepository()
    test_result_obj = EvaluationResult(
        case_id="test_001",
        model_name="gpt-4",
        adapter_name="finance_adapter",
        status=EvaluationStatus.PASSED,
        latency_ms=120.5,
        response=DomainResponse(is_valid=True, text="ok", score=0.95),
    )

    record_id = repo.save(test_result_obj)

    from src.infra.db.models import EvaluationResultModel
    from src.infra.db.session import SessionLocal

    db = SessionLocal()
    try:
        row = db.query(EvaluationResultModel).filter_by(id=record_id).one()
        assert row.case_id == "test_001"
        assert row.status == "passed"
        assert row.response_data["score"] == 0.95
    finally:
        db.close()
