import pytest
from src.infra.db.models import EvaluationResultModel
from src.workers.tasks import buffer_service


@pytest.fixture(autouse=True)
def clear_buffer():
    """确保每个测试用例缓冲区干净"""
    buffer_service.buffer.clear()


def test_buffer_threshold_trigger(db_session):
    # 1. 业务逻辑层测试：直接操作 Service 单例
    for i in range(1000):
        buffer_service.add(EvaluationResultModel(case_id=f"BATCH_{i}", status="pending"))

    assert len(buffer_service.buffer) == 1000

    # 2. 落盘逻辑测试：注入测试用的 session
    buffer_service.flush(db_session=db_session)

    # 3. 数据一致性校验
    db_session.expire_all()
    count = db_session.query(EvaluationResultModel).count()
    assert count == 1000
