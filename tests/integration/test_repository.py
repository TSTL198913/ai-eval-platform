from src.infra.analytics.analytics import QueryService
from src.infra.db.models import EvaluationResultModel
from src.infra.db.repository import EvaluationRepository
from src.schemas.evaluation import DomainResponse
from src.schemas.schemas import EvaluationResult, EvaluationStatus


def test_repository_persists_and_queryable_fields():
    repo = EvaluationRepository()
    record_id = repo.save(
        EvaluationResult(
            case_id="repo_case_001",
            status=EvaluationStatus.PASSED,
            model_name="mock-model",
            adapter_name="TextMatchEvaluator",
            response=DomainResponse(is_valid=True, text="answer", score=0.91),
            latency_ms=88.0,
        )
    )

    from src.infra.db.session import SessionLocal

    db = SessionLocal()
    try:
        row = db.query(EvaluationResultModel).filter_by(id=record_id).one()
        assert row.case_id == "repo_case_001"
        assert row.status == "passed"
        assert row.latency_ms == 88.0
        assert row.response_data["score"] == 0.91

        report = QueryService(db).get_performance_report()
        assert report["total_evals"] >= 1
        assert report["success_rate"] > 0
        assert report["avg_latency_ms"] > 0
    finally:
        db.close()
