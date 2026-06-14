"""真 Redis + Celery Worker 异步链路（非 eager 模式）。"""

import os
import time

import pytest
from src.workers.celery_app import celery_app
from src.workers.tasks import eval_case_task

pytestmark = [pytest.mark.redis, pytest.mark.integration]


@pytest.fixture
def redis_broker_url():
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        import redis

        client = redis.from_url(url, protocol=2)
        client.ping()
    except Exception as exc:
        pytest.skip(f"Redis 不可用: {exc}")
    return url


@pytest.fixture
def celery_real_mode(redis_broker_url, monkeypatch, mock_llm):
    from src.domain.models import llm_factory

    monkeypatch.setattr(llm_factory, "create_llm_client", lambda client=None: mock_llm)
    mock_llm.chat.return_value = "利息为30元，本金1000元。"

    backend_url = redis_broker_url.replace("/0", "/1")
    if backend_url == redis_broker_url:
        backend_url = f"{redis_broker_url}/1"

    celery_app.conf.update(
        broker_url=redis_broker_url,
        result_backend=backend_url,
        task_always_eager=False,
        task_eager_propagates=False,
        task_store_eager_result=True,
        broker_transport_options={"protocol": 2},
        result_backend_transport_options={"protocol": 2},
    )
    yield
    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
        result_backend="cache+memory://",
    )


def test_task_executes_through_redis_broker(celery_real_mode):
    case_data = {
        "id": f"redis_case_{int(time.time())}",
        "type": "finance",
        "payload": {
            "user_input": "1000元贷款年化3%一年利息",
            "expected_output": "30",
        },
        "metadata": {},
    }

    async_result = eval_case_task.apply_async(args=[case_data])
    payload = async_result.get(timeout=30)

    assert payload["status"] == "success"
    assert payload["case_id"] == case_data["id"]
    assert payload["evaluation_status"] == "passed"
    assert payload["latency_ms"] >= 0
