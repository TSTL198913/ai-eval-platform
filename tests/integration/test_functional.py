import pytest

from src.infra.db.models import EvaluationResultModel
from src.infra.db.session import get_db_session, init_tables
from src.workers.tasks import buffer_service


@pytest.fixture(autouse=True)
def clear_buffer():
    """确保每个测试用例缓冲区干净"""
    buffer_service.buffer.clear()


@pytest.fixture(autouse=True)
def setup_database():
    """初始化数据库表"""
    init_tables()
    yield


@pytest.mark.slow
def test_buffer_threshold_trigger():
    for i in range(100):
        buffer_service.add(EvaluationResultModel(case_id=f"BATCH_{i}", status="pending"))

    assert len(buffer_service.buffer) == 100

    with get_db_session() as db_session:
        buffer_service.flush(db_session=db_session)

        db_session.expire_all()
        count = db_session.query(EvaluationResultModel).count()
        assert count == 100
