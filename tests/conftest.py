import os
import sys
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

# 测试环境使用 SQLite，避免强依赖 PostgreSQL
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
        skip_redis = pytest.mark.skip(
            reason="跳过 redis 用例，需 REDIS_URL 或 CI Worker"
        )
        for item in items:
            if "redis" in item.keywords:
                item.add_marker(skip_redis)


@pytest.fixture(scope="session", autouse=True)
def init_db_tables():
    from src.infra.db.session import engine

    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def mock_llm():
    """统一 Mock LLM，避免测试依赖真实 API。"""
    client = MagicMock()
    client.chat.return_value = (
        "利息为30元。语法正确，结构清晰，机器学习是人工智能的重要分支。"
    )
    client.config.model_name = "mock-model"
    return client


@pytest.fixture
def mock_evaluation_schema():
    def _create(id="001", type="general", **kwargs):
        return EvaluationSchema(
            id=id,
            type=type,
            payload=kwargs.get("payload", {"case_id": id}),
            metadata=kwargs.get("metadata", {}),
        )

    return _create


@pytest.fixture(scope="session")
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def setup_celery_test_mode(request):
    if request.node.get_closest_marker("redis"):
        yield
        return

    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
        task_store_eager_result=True,
        result_backend="cache+memory://",
    )
    yield


@pytest.fixture(autouse=True)
def clean_db(db_session):
    """清理 fixture 专用 DB。"""
    engine = db_session.get_bind()
    inspector = inspect(engine)

    db_session.execute(text("PRAGMA foreign_keys = OFF;"))
    for table in inspector.get_table_names():
        if table != "sqlite_sequence":
            db_session.execute(text(f"DELETE FROM {table};"))
    db_session.execute(text("PRAGMA foreign_keys = ON;"))
    db_session.commit()
    yield
    db_session.rollback()


@pytest.fixture(autouse=True)
def clean_buffer():
    from src.workers.tasks import buffer_service

    buffer_service.buffer.clear()
    yield
    buffer_service.buffer.clear()


@pytest.fixture(autouse=True)
def clean_global_db():
    """清理 Repository / SessionLocal 使用的全局引擎数据。"""
    from src.infra.db.session import SessionLocal

    db = SessionLocal()
    try:
        inspector = inspect(db.get_bind())
        for table in inspector.get_table_names():
            if table != "sqlite_sequence":
                db.execute(text(f"DELETE FROM {table};"))
        db.commit()
    finally:
        db.close()
    yield
