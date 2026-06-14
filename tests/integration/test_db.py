import pytest
from sqlalchemy import text

from src.infra.db.session import SessionLocal, engine, get_db_session


def test_db_connection_success():
    """验证基础设施：连接池是否可提供有效连接"""
    with get_db_session() as session:
        result = session.execute(text("SELECT 1"))
        assert result.scalar() == 1


def test_transaction_rollback_on_failure():
    """验证防御性：发生异常时，Session 是否自动回滚并释放连接"""
    # 构造一个非法操作，触发数据库异常
    with pytest.raises(Exception):
        with get_db_session() as session:
            session.execute(text("SELECT * FROM non_existent_table"))

    # 验证 Session 的连接池状态是否健康
    # 如果没回滚或者连接没关闭，后续操作会失败
    with get_db_session() as session:
        result = session.execute(text("SELECT 1"))
        assert result.scalar() == 1


# tests/infra/test_db.py


# tests/infra/test_db.py


# tests/infra/test_db.py


def test_session_closure():
    """验证 Session 关闭后连接可继续复用。"""
    pool = engine.pool
    if not hasattr(pool, "checkedout"):
        pytest.skip("当前数据库连接池不支持 checkedout 统计")

    initial_checkedout = pool.checkedout()

    session = SessionLocal()
    session.begin()
    session.execute(text("SELECT 1"))

    assert pool.checkedout() > initial_checkedout
    session.close()
    assert pool.checkedout() == initial_checkedout
