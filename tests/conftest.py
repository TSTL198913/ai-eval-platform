import asyncio
import os
import sys
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("TESTING", "1")
os.environ.setdefault("TEST_DATABASE_URL", "sqlite:///:memory:")

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
    parser.addoption(
        "--priority",
        action="store",
        default=None,
        help="按优先级运行测试用例 (p0/p1/p2)",
        choices=["p0", "p1", "p2"],
    )
    parser.addoption(
        "--ci-mode",
        action="store_true",
        default=False,
        help="CI模式：运行所有关键测试，跳过slow用例",
    )


def pytest_collection_modifyitems(config, items):
    ci_mode = config.getoption("--ci-mode")
    priority = config.getoption("--priority")

    if not config.getoption("--run-slow") and not ci_mode:
        skip_slow = pytest.mark.skip(reason="跳过 slow 用例，使用 --run-slow 启用")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)

    if not os.getenv("REDIS_URL") and not os.getenv("CI"):
        skip_redis = pytest.mark.skip(reason="跳过 redis 用例，需 REDIS_URL 或 CI Worker")
        for item in items:
            if "redis" in item.keywords:
                item.add_marker(skip_redis)

    if priority:
        skip_priority = pytest.mark.skip(reason=f"跳过非{priority}优先级用例")
        for item in items:
            if priority not in item.keywords:
                item.add_marker(skip_priority)

    if ci_mode:
        skip_e2e = pytest.mark.skip(reason="CI模式跳过e2e测试")
        for item in items:
            if "e2e" in str(item.fspath):
                item.add_marker(skip_e2e)


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="function")
def mock_llm():
    client = MagicMock()
    client.chat.return_value = "利息为30元。语法正确，结构清晰，机器学习是人工智能的重要分支。"
    client.config.model_name = "mock-model"
    return client


@pytest.fixture
def mock_evaluation_result_model():
    """Mock EvaluationResultModel for tests that don't need real DB"""
    from unittest.mock import MagicMock

    class MockModel:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

        def to_dict(self):
            return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}

    return MockModel


@pytest.fixture(autouse=True)
def reset_buffer_service():
    """每个测试后重置 buffer_service"""
    yield
    try:
        from src.workers.tasks import buffer_service
        with buffer_service._lock:
            buffer_service.buffer = []
    except Exception:
        pass