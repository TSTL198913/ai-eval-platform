"""
混沌工程测试 - 网络抖动场景验证
=====================================
在Toxiproxy注入的50ms-200ms网络抖动下验证系统的弹性恢复能力。
"""

import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


import httpx
import pytest
import redis

from src.domain.evaluators.security import SecurityEvaluator
from src.infra.db.session import get_db_session
from src.schemas.evaluation import EvaluationSchema


class TestChaosNetworkJitter:
    """网络抖动场景测试"""

    @pytest.fixture(scope="class")
    def redis_client(self):
        """创建Redis客户端（通过Toxiproxy）"""
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        return redis.Redis.from_url(redis_url, decode_responses=True)

    @pytest.fixture(scope="class")
    def http_client(self):
        """创建HTTP客户端"""
        return httpx.Client(base_url="http://localhost:8000", timeout=30)

    def test_redis_connectivity_with_jitter(self, redis_client):
        """验证Redis连接在网络抖动下仍然可用"""
        try:
            result = redis_client.ping()
            assert result is True, "Redis ping failed"
        except Exception as e:
            pytest.fail(f"Redis connectivity test failed: {e}")

    def test_redis_set_get_with_jitter(self, redis_client):
        """验证Redis读写在网络抖动下的正确性"""
        test_key = "chaos:test:key"
        test_value = "chaos_test_value"

        redis_client.set(test_key, test_value)
        result = redis_client.get(test_key)

        assert result == test_value, f"Expected '{test_value}', got '{result}'"
        redis_client.delete(test_key)

    def test_redis_timeout_handling(self, redis_client):
        """验证Redis超时处理"""
        start = time.time()
        try:
            result = redis_client.ping()
            elapsed = time.time() - start

            assert result is True
            assert elapsed < 5.0, f"Redis ping took {elapsed:.2f}s, timeout likely"
        except Exception as e:
            pytest.fail(f"Redis timeout handling failed: {e}")

    def test_health_endpoint_with_jitter(self, http_client):
        """验证健康检查端点在网络抖动下的响应"""
        try:
            response = http_client.get("/health")
            assert response.status_code == 200, f"Health check failed: {response.status_code}"
            data = response.json()
            assert "status" in data, "Health response missing status field"
        except httpx.TimeoutException:
            pytest.fail("Health endpoint timed out")
        except Exception as e:
            pytest.fail(f"Health endpoint test failed: {e}")

    def test_evaluate_endpoint_with_jitter(self, http_client):
        """验证评测端点在网络抖动下的响应"""
        try:
            payload = {
                "id": "chaos-test-request",
                "type": "security",
                "payload": {"user_input": "test input"},
            }
            response = http_client.post("/api/v1/evaluate", json=payload)
            assert response.status_code in [200, 201], f"Evaluate failed: {response.status_code}"
        except httpx.TimeoutException:
            pytest.fail("Evaluate endpoint timed out")
        except Exception as e:
            pytest.fail(f"Evaluate endpoint test failed: {e}")

    def test_redis_pipeline_with_jitter(self, redis_client):
        """验证Redis管道操作在网络抖动下的正确性"""
        pipe = redis_client.pipeline()
        for i in range(10):
            pipe.set(f"chaos:pipe:{i}", f"value:{i}")

        start = time.time()
        results = pipe.execute()
        elapsed = time.time() - start

        assert all(results), "Pipeline execution failed"
        assert elapsed < 10.0, f"Pipeline took {elapsed:.2f}s, timeout likely"

        for i in range(10):
            redis_client.delete(f"chaos:pipe:{i}")

    def test_database_connectivity_with_jitter(self):
        """验证数据库连接在网络抖动下仍然可用"""
        try:
            with get_db_session() as session:
                session.execute("SELECT 1")
                session.commit()
        except Exception as e:
            pytest.fail(f"Database connectivity test failed: {e}")

    def test_security_evaluator_resilience(self):
        """验证安全评估器在网络抖动下的弹性"""
        evaluator = SecurityEvaluator()
        request = EvaluationSchema(
            id="chaos-security-test",
            type="security",
            payload={"user_input": "test security evaluation"},
        )

        start = time.time()
        result = evaluator.safe_evaluate(request)
        elapsed = time.time() - start

        assert isinstance(result, evaluator.response_class), "Evaluator returned invalid response"
        assert result.is_valid is not None, "Evaluator result is invalid"
        assert elapsed < 15.0, f"Evaluator took {elapsed:.2f}s, timeout likely"

    def test_concurrent_redis_operations(self, redis_client):
        """验证并发Redis操作在网络抖动下的正确性"""
        import threading

        results = []

        def set_key(i):
            try:
                redis_client.set(f"chaos:concurrent:{i}", f"value:{i}")
                results.append(("success", i))
            except Exception as e:
                results.append(("error", i, str(e)))

        threads = []
        for i in range(20):
            t = threading.Thread(target=set_key, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=10)

        success_count = sum(1 for r in results if r[0] == "success")
        assert success_count == 20, f"Only {success_count}/20 concurrent operations succeeded"

        for i in range(20):
            redis_client.delete(f"chaos:concurrent:{i}")

    def test_idempotency_checker_with_jitter(self, http_client):
        """验证幂等性检查器在网络抖动下的正确性"""
        try:
            payload = {
                "id": "chaos-idempotency-test",
                "type": "security",
                "payload": {"user_input": "idempotency test"},
            }

            response1 = http_client.post("/api/v1/evaluate", json=payload)
            response2 = http_client.post("/api/v1/evaluate", json=payload)

            assert response1.status_code == response2.status_code, "Idempotency failed"
        except Exception as e:
            pytest.fail(f"Idempotency test failed: {e}")

    def test_evaluator_factory_with_jitter(self):
        """验证评估器工厂在网络抖动下的正确性"""
        from src.domain.evaluators.base import EvaluatorFactory

        evaluator = EvaluatorFactory.get("security")
        assert evaluator is not None, "Evaluator factory failed"


class TestChaosEdgeCases:
    """边界情况混沌测试"""

    def test_empty_request_with_jitter(self, http_client):
        """验证空请求在网络抖动下的处理"""
        try:
            response = http_client.post("/api/v1/evaluate", json={})
            assert response.status_code in [400, 200], f"Unexpected status: {response.status_code}"
        except Exception as e:
            pytest.fail(f"Empty request test failed: {e}")

    def test_large_payload_with_jitter(self, http_client):
        """验证大请求在网络抖动下的处理"""
        try:
            large_input = "x" * 10000
            payload = {
                "id": "chaos-large-test",
                "type": "security",
                "payload": {"user_input": large_input},
            }

            response = http_client.post("/api/v1/evaluate", json=payload, timeout=60)
            assert response.status_code in [
                200,
                201,
            ], f"Large payload failed: {response.status_code}"
        except httpx.TimeoutException:
            pytest.fail("Large payload request timed out")
        except Exception as e:
            pytest.fail(f"Large payload test failed: {e}")


pytestmark = pytest.mark.chaos
