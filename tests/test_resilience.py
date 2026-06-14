from unittest.mock import MagicMock

import pytest

from src.infra.db.models import EvaluationResultModel
from src.workers.tasks import buffer_service


@pytest.fixture(autouse=True)
def clean_buffer():
    buffer_service.buffer.clear()
    yield


def test_db_failure_recovery_chaos():
    for i in range(100):
        buffer_service.add(
            EvaluationResultModel(case_id=f"CHAOS_{i}", status="pending")
        )

    mock_db = MagicMock()
    mock_db.bulk_save_objects.side_effect = Exception("Database Connection Lost!")

    with pytest.raises(Exception, match="Database Connection Lost"):
        buffer_service.flush(db_session=mock_db)

    assert len(buffer_service.buffer) == 100


def test_flush_success_clears_buffer(db_session):
    buffer_service.add(
        EvaluationResultModel(case_id="FLUSH_1", status="passed")
    )
    buffer_service.flush(db_session=db_session)
    assert len(buffer_service.buffer) == 0
    assert db_session.query(EvaluationResultModel).count() == 1


def test_concurrent_write_safety():
    import threading

    def write_task():
        for _ in range(500):
            buffer_service.add(
                EvaluationResultModel(case_id="CONC", status="pending")
            )

    threads = [threading.Thread(target=write_task) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(buffer_service.buffer) == 5000
