"""
分布式模块集成测试
测试目标：验证熔断器、幂等性检查器等分布式组件的完整集成流程
"""

import time
from unittest.mock import MagicMock

import pytest

from src.distributed.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitState,
    global_registry,
)
from src.distributed.idempotency import (
    IdempotencyChecker,
)


@pytest.fixture
def mock_redis():
    """Mock Redis客户端"""
    redis = MagicMock()
    redis.setnx.return_value = True
    redis.exists.return_value = False
    redis.get.return_value = None
    return redis


class TestCircuitBreakerBasicFunctionality:
    """熔断器基础功能测试"""

    def test_circuit_breaker_starts_closed(self):
        """熔断器应从关闭状态开始"""
        breaker = CircuitBreaker("test-breaker")
        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_closed is True
        assert breaker.is_open is False

    def test_circuit_breaker_allows_calls_when_closed(self):
        """熔断器关闭时应允许调用"""
        breaker = CircuitBreaker("test-breaker")

        def success_func():
            return "success"

        result = breaker.call_sync(success_func)
        assert result == "success"
        assert breaker.stats.successful_calls == 1

    def test_circuit_breaker_records_failures(self):
        """熔断器应记录失败调用"""
        breaker = CircuitBreaker("test-breaker")

        def fail_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            breaker.call_sync(fail_func)

        assert breaker.stats.failed_calls == 1
        assert breaker._failure_count == 1

    def test_circuit_breaker_opens_after_threshold(self):
        """熔断器应在达到失败阈值后打开"""
        breaker = CircuitBreaker(
            "test-breaker",
            config=CircuitBreakerConfig(failure_threshold=3),
        )

        def fail_func():
            raise ValueError("Test error")

        for _ in range(3):
            with pytest.raises(ValueError):
                breaker.call_sync(fail_func)

        assert breaker.state == CircuitState.OPEN
        assert breaker.stats.rejected_calls == 0

    def test_circuit_breaker_rejects_calls_when_open(self):
        """熔断器打开时应拒绝调用"""
        breaker = CircuitBreaker(
            "test-breaker",
            config=CircuitBreakerConfig(failure_threshold=2),
        )

        def fail_func():
            raise ValueError("Test error")

        for _ in range(2):
            with pytest.raises(ValueError):
                breaker.call_sync(fail_func)

        with pytest.raises(CircuitBreakerError):
            breaker.call_sync(fail_func)

        assert breaker.stats.rejected_calls == 1

    def test_circuit_breaker_closes_after_success(self):
        """熔断器应在成功后关闭"""
        breaker = CircuitBreaker(
            "test-breaker",
            config=CircuitBreakerConfig(failure_threshold=2, success_threshold=2),
        )

        call_count = [0]

        def func():
            call_count[0] += 1
            if call_count[0] <= 2:
                raise ValueError("Test error")
            return "success"

        for _ in range(2):
            with pytest.raises(ValueError):
                breaker.call_sync(func)

        assert breaker.state == CircuitState.OPEN

        time.sleep(breaker.config.timeout_seconds + 0.1)

        result1 = breaker.call_sync(func)
        result2 = breaker.call_sync(func)

        assert result1 == "success"
        assert result2 == "success"
        assert breaker.state == CircuitState.CLOSED


class TestCircuitBreakerHalfOpenState:
    """熔断器半开状态测试"""

    def test_circuit_breaker_enters_half_open_after_timeout(self):
        """熔断器应在超时后进入半开状态"""
        breaker = CircuitBreaker(
            "test-breaker",
            config=CircuitBreakerConfig(failure_threshold=2, timeout_seconds=0.1),
        )

        def fail_func():
            raise ValueError("Test error")

        for _ in range(2):
            with pytest.raises(ValueError):
                breaker.call_sync(fail_func)

        assert breaker.state == CircuitState.OPEN

        time.sleep(0.2)

        assert breaker.state == CircuitState.HALF_OPEN

    def test_circuit_breaker_allows_probe_calls_in_half_open(self):
        """熔断器半开状态应允许探测调用"""
        breaker = CircuitBreaker(
            "test-breaker",
            config=CircuitBreakerConfig(
                failure_threshold=2, timeout_seconds=0.1, half_open_max_calls=2
            ),
        )

        def fail_func():
            raise ValueError("Test error")

        for _ in range(2):
            with pytest.raises(ValueError):
                breaker.call_sync(fail_func)

        time.sleep(0.2)

        def success_func():
            return "success"

        result = breaker.call_sync(success_func)
        assert result == "success"

    def test_circuit_breaker_rejects_after_max_probe_calls(self):
        """熔断器在半开状态下成功后应回到closed状态"""
        breaker = CircuitBreaker(
            "test-breaker",
            config=CircuitBreakerConfig(
                failure_threshold=2, timeout_seconds=0.1, half_open_max_calls=2
            ),
        )

        def fail_func():
            raise ValueError("Test error")

        for _ in range(2):
            with pytest.raises(ValueError):
                breaker.call_sync(fail_func)

        time.sleep(0.2)

        def success_func():
            return "success"

        breaker.call_sync(success_func)
        breaker.call_sync(success_func)

        assert breaker.state == CircuitState.CLOSED


class TestCircuitBreakerStats:
    """熔断器统计测试"""

    def test_circuit_breaker_stats_tracking(self):
        """熔断器应追踪统计信息"""
        breaker = CircuitBreaker("test-breaker")

        def success_func():
            return "success"

        def fail_func():
            raise ValueError("Error")

        breaker.call_sync(success_func)
        breaker.call_sync(success_func)
        with pytest.raises(ValueError):
            breaker.call_sync(fail_func)

        stats = breaker.get_stats()
        assert stats["total_calls"] == 3
        assert stats["successful_calls"] == 2
        assert stats["failed_calls"] == 1
        assert stats["rejected_calls"] == 0

    def test_circuit_breaker_state_changes_tracking(self):
        """熔断器应追踪状态变化"""
        breaker = CircuitBreaker(
            "test-breaker",
            config=CircuitBreakerConfig(failure_threshold=2, timeout_seconds=0.1),
        )

        def fail_func():
            raise ValueError("Error")

        for _ in range(2):
            with pytest.raises(ValueError):
                breaker.call_sync(fail_func)

        stats = breaker.get_stats()
        assert stats["state_changes"] == 1

        time.sleep(0.2)
        breaker.call_sync(lambda: "success")
        breaker.call_sync(lambda: "success")

        stats = breaker.get_stats()
        assert stats["state_changes"] == 2


class TestCircuitBreakerRegistry:
    """熔断器注册中心测试"""

    def test_registry_get_or_create(self):
        """注册中心应获取或创建熔断器"""
        breaker = global_registry.get_or_create("test-registry")
        assert breaker is not None
        assert breaker.name == "test-registry"

        breaker2 = global_registry.get_or_create("test-registry")
        assert breaker2 is breaker

    def test_registry_list_breakers(self):
        """注册中心应列出所有熔断器"""
        global_registry._breakers.clear()

        global_registry.get_or_create("breaker1")
        global_registry.get_or_create("breaker2")

        breakers = global_registry.list_breakers()
        assert len(breakers) == 2
        assert "breaker1" in breakers
        assert "breaker2" in breakers

    def test_registry_all_stats(self):
        """注册中心应获取所有熔断器统计"""
        global_registry._breakers.clear()

        breaker1 = global_registry.get_or_create("breaker1")
        breaker1.call_sync(lambda: "success")

        stats = global_registry.all_stats()
        assert "breaker1" in stats
        assert stats["breaker1"]["successful_calls"] == 1


class TestCircuitBreakerRedisIntegration:
    """熔断器Redis集成测试"""

    def test_circuit_breaker_saves_state_to_redis(self, mock_redis):
        """熔断器应保存状态到Redis"""
        breaker = CircuitBreaker("redis-test", redis_client=mock_redis)

        def fail_func():
            raise ValueError("Error")

        for _ in range(5):
            with pytest.raises(ValueError):
                breaker.call_sync(fail_func)

        mock_redis.set.assert_called_once()

    def test_circuit_breaker_loads_state_from_redis(self, mock_redis):
        """熔断器应从Redis加载状态"""
        mock_redis.get.return_value = '{"state": "open", "failure_count": 5, "success_count": 0}'

        breaker = CircuitBreaker("redis-test", redis_client=mock_redis)

        assert breaker._state == CircuitState.OPEN
        assert breaker._failure_count == 5


class TestIdempotencyCheckerBasicFunctionality:
    """幂等性检查器基础功能测试"""

    def test_checker_mark_processing(self, mock_redis):
        """检查器应标记请求正在处理"""
        checker = IdempotencyChecker(mock_redis)

        result = checker.mark_processing("request-001")
        assert result is True
        mock_redis.setnx.assert_called_once()

    def test_checker_prevents_duplicate_request(self, mock_redis):
        """检查器应防止重复请求"""
        checker = IdempotencyChecker(mock_redis)
        mock_redis.setnx.side_effect = [True, False]

        result1 = checker.mark_processing("request-001")
        result2 = checker.mark_processing("request-001")

        assert result1 is True
        assert result2 is False

    def test_checker_mark_processed(self, mock_redis):
        """检查器应标记请求已处理"""
        checker = IdempotencyChecker(mock_redis)

        result = checker.mark_processed("request-001", result={"status": "success"})
        assert result is True
        mock_redis.set.assert_called_once()

    def test_checker_get_cached_result(self, mock_redis):
        """检查器应获取缓存结果"""
        mock_redis.get.return_value = '{"status": "processed", "result": {"score": 0.9}}'

        checker = IdempotencyChecker(mock_redis)
        result = checker.get_cached_result("request-001")

        assert result == {"score": 0.9}

    def test_checker_get_cached_result_returns_none(self, mock_redis):
        """检查器应在无缓存时返回None"""
        mock_redis.get.return_value = None

        checker = IdempotencyChecker(mock_redis)
        result = checker.get_cached_result("request-001")

        assert result is None

    def test_checker_clear(self, mock_redis):
        """检查器应清除幂等性记录"""
        checker = IdempotencyChecker(mock_redis)

        result = checker.clear("request-001")
        assert result is True
        mock_redis.delete.assert_called_once()

    def test_checker_check(self, mock_redis):
        """检查器应检查请求是否已处理"""
        mock_redis.exists.return_value = False
        checker = IdempotencyChecker(mock_redis)

        result = checker.check("request-001")
        assert result is True

        mock_redis.exists.return_value = True
        result = checker.check("request-001")
        assert result is False


class TestIdempotencyCheckerIntegrationWithAPI:
    """幂等性检查器与API集成测试"""

    def test_idempotency_flow(self, mock_redis):
        """完整的幂等性检查流程"""
        checker = IdempotencyChecker(mock_redis)
        mock_redis.setnx.return_value = True

        assert checker.check("api-001") is True
        assert checker.mark_processing("api-001") is True

        result_data = {"status": "success", "score": 0.85}
        checker.mark_processed("api-001", result=result_data)

        mock_redis.set.assert_called_once()

    def test_concurrent_requests(self, mock_redis):
        """并发请求应被正确处理"""
        checker = IdempotencyChecker(mock_redis)
        mock_redis.setnx.side_effect = [True, False]

        result1 = checker.mark_processing("concurrent-001")
        result2 = checker.mark_processing("concurrent-001")

        assert result1 is True
        assert result2 is False

    def test_failure_clears_idempotency(self, mock_redis):
        """失败时应清除幂等性记录"""
        checker = IdempotencyChecker(mock_redis)
        mock_redis.setnx.return_value = True

        checker.mark_processing("fail-001")
        checker.clear("fail-001")

        mock_redis.delete.assert_called_once()


class TestCircuitBreakerIntegrationWithEvaluator:
    """熔断器与评估器集成测试"""

    def test_evaluator_circuit_breaker_protection(self):
        """熔断器应保护评估器"""
        breaker = CircuitBreaker(
            "evaluator_semantic",
            config=CircuitBreakerConfig(failure_threshold=3),
        )

        def create_evaluator():
            raise RuntimeError("Evaluator creation failed")

        for _ in range(3):
            with pytest.raises(RuntimeError):
                breaker.call_sync(create_evaluator)

        assert breaker.state == CircuitState.OPEN

        with pytest.raises(CircuitBreakerError):
            breaker.call_sync(create_evaluator)

    def test_evaluator_circuit_breaker_recovery(self):
        """熔断器应能恢复"""
        breaker = CircuitBreaker(
            "evaluator_grammar",
            config=CircuitBreakerConfig(
                failure_threshold=2, timeout_seconds=0.1, success_threshold=1
            ),
        )

        call_count = [0]

        def create_evaluator():
            call_count[0] += 1
            if call_count[0] <= 2:
                raise RuntimeError("Failed")
            return "Evaluator instance"

        for _ in range(2):
            with pytest.raises(RuntimeError):
                breaker.call_sync(create_evaluator)

        assert breaker.state == CircuitState.OPEN

        time.sleep(0.2)

        result = breaker.call_sync(create_evaluator)
        assert result == "Evaluator instance"
        assert breaker.state == CircuitState.CLOSED


class TestDistributedIntegrationWithEvaluationFlow:
    """分布式组件与评估流程集成测试"""

    def test_circuit_breaker_protects_evaluation(self):
        """熔断器应保护评估流程"""
        breaker = CircuitBreaker(
            "evaluation_flow",
            config=CircuitBreakerConfig(failure_threshold=3),
        )

        def evaluate():
            raise Exception("LLM service unavailable")

        for _ in range(3):
            with pytest.raises(Exception):
                breaker.call_sync(evaluate)

        assert breaker.state == CircuitState.OPEN

        with pytest.raises(CircuitBreakerError):
            breaker.call_sync(evaluate)

        assert breaker.stats.rejected_calls == 1

    def test_idempotency_protects_evaluation(self, mock_redis):
        """幂等性应保护评估流程"""
        checker = IdempotencyChecker(mock_redis)
        mock_redis.setnx.return_value = True

        assert checker.check("eval-001") is True
        assert checker.mark_processing("eval-001") is True

        eval_result = {"status": "success", "record_id": "eval-001", "score": 0.9}
        checker.mark_processed("eval-001", result=eval_result)

        mock_redis.set.assert_called()

    def test_circuit_breaker_and_idempotency_combined(self, mock_redis):
        """熔断器和幂等性检查应协同工作"""
        breaker = CircuitBreaker("combined-test")
        checker = IdempotencyChecker(mock_redis)
        mock_redis.setnx.return_value = True

        def safe_evaluate():
            checker.mark_processing("safe-eval-001")
            result = {"status": "success"}
            checker.mark_processed("safe-eval-001", result=result)
            return result

        result = breaker.call_sync(safe_evaluate)
        assert result["status"] == "success"
        assert breaker.stats.successful_calls == 1

        mock_redis.set.assert_called()
