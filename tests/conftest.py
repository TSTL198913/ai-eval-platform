import asyncio
import os
import sys
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("TESTING", "1")
os.environ.setdefault("TEST_DATABASE_URL", "sqlite:///:memory:")

from src.infra.db.session import Base  # noqa: E402
from src.schemas.evaluation import EvaluationSchema  # noqa: E402
from src.workers.celery_app import celery_app  # noqa: E402

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def pytest_addoption(parser):
    parser.addoption(
        "--run-slow",
        action="store_true",
        default=False,
        help="运行标记为 slow 的压测用例",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-slow"):
        return
    skip_slow = pytest.mark.skip(reason="跳过 slow 用例，使用 --run-slow 启用")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)

    if not os.getenv("REDIS_URL") and not os.getenv("CI"):
        skip_redis = pytest.mark.skip(reason="跳过 redis 用例，需 REDIS_URL 或 CI Worker")
        for item in items:
            if "redis" in item.keywords:
                item.add_marker(skip_redis)


@pytest.fixture(scope="session", autouse=True)
def init_db_tables():
    from src.infra.db.session import engine

    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture(scope="session")
def db_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def db_session(db_engine):
    from sqlalchemy import event

    Session = sessionmaker(bind=db_engine)
    session = Session()

    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(session, transaction):
        if transaction.nested and not transaction._parent.nested:
            session.begin_nested()

    yield session

    session.rollback()
    session.close()


@pytest.fixture(autouse=True, scope="function")
def setup_celery_test_mode():
    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
        task_store_eager_result=True,
        result_backend="cache+memory://",
        broker_url="memory://",
    )
    yield


@pytest.fixture(autouse=True, scope="function")
def clean_buffer():
    from src.workers.tasks import buffer_service

    buffer_service.buffer.clear()
    yield
    buffer_service.buffer.clear()


@pytest.fixture(autouse=True, scope="function")
def clean_global_db():
    from src.infra.db.session import get_session_local

    db = get_session_local()()
    try:
        inspector = inspect(db.get_bind())
        db.execute(text("PRAGMA foreign_keys = OFF;"))
        for table in inspector.get_table_names():
            if table != "sqlite_sequence":
                db.execute(text(f"DELETE FROM {table};"))
        db.execute(text("PRAGMA foreign_keys = ON;"))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="function")
def mock_llm():
    client = MagicMock()
    client.chat.return_value = "利息为30元。语法正确，结构清晰，机器学习是人工智能的重要分支。"
    client.config.model_name = "mock-model"
    return client


@pytest.fixture(scope="function")
def mock_evaluation_schema():
    def _create(id="001", type="general", **kwargs):
        return EvaluationSchema(
            id=id,
            type=type,
            payload=kwargs.get("payload", {"case_id": id}),
            metadata=kwargs.get("metadata", {}),
        )

    return _create
