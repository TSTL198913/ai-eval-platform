"""
评估器并发安全专项测试
测试目标：验证评估器在多线程/多协程场景下的共享状态访问安全性
关键发现：测试熔断器状态切换、评估器缓存、线程安全锁保护
"""

import asyncio
import threading
import time

import pytest

from src.distributed.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitState,
)
from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.evaluators.security import SecurityEvaluator


class TestCircuitBreakerThreadSafety:
    """熔断器线程安全测试"""

    def test_breaker_state_transition_thread_safe(self):
        """熔断器状态转换应线程安全"""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout_seconds=1.0,
            half_open_max_calls=5,
        )
        breaker = CircuitBreaker("test_thread_safe", config)

        results = []
        lock = threading.Lock()

        def worker(id):
            for _ in range(5):
                try:
                    breaker.call_sync(lambda: 1 / 0)
                except (ZeroDivisionError, CircuitBreakerError):
                    pass
                time.sleep(0.01)
            with lock:
                results.append((id, breaker.state.value))

        threads = []
        for i in range(10):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert breaker.state == CircuitState.OPEN
        assert breaker.stats.failed_calls >= 3
        assert breaker.stats.total_calls >= 3

    def test_breaker_concurrent_access(self):
        """多个线程同时访问熔断器应保持状态一致性"""
        config = CircuitBreakerConfig(
            failure_threshold=10,
            success_threshold=2,
            timeout_seconds=5.0,
        )
        breaker = CircuitBreaker("test_concurrent", config)

        success_count = [0]
        lock = threading.Lock()

        def successful_worker(id):
            for _ in range(20):
                breaker.call_sync(lambda: f"success_{id}")
                with lock:
                    success_count[0] += 1
                time.sleep(0.001)

        threads = []
        for i in range(5):
            t = threading.Thread(target=successful_worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert breaker.state == CircuitState.CLOSED
        assert breaker.stats.successful_calls == 100
        assert breaker.stats.total_calls == 100
        assert success_count[0] == 100


class TestEvaluatorThreadSafety:
    """评估器线程安全测试"""

    def test_shared_evaluator_instance_concurrent_access(self):
        """共享评估器实例应支持并发访问"""
        evaluator = SecurityEvaluator()

        results = []
        lock = threading.Lock()

        def worker(id):
            from src.schemas.evaluation import EvaluationSchema

            request = EvaluationSchema(
                id=f"test-{id}",
                type="security",
                payload={
                    "user_input": f"Test input {id}",
                },
            )
            result = evaluator.evaluate(request)
            with lock:
                results.append(result)

        threads = []
        for i in range(10):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(results) == 10
        for result in results:
            assert result.is_valid is True
            assert result.score >= 0

    def test_breaker_cache_thread_safe(self):
        """评估器熔断器缓存应线程安全"""
        breakers = []
        lock = threading.Lock()

        def create_breaker(id):
            evaluator = SecurityEvaluator()
            breaker = evaluator._get_breaker()
            with lock:
                breakers.append(breaker)

        threads = []
        for i in range(10):
            t = threading.Thread(target=create_breaker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(set(breakers)) == 1


class TestCircuitBreakerAsyncSafety:
    """熔断器异步安全测试"""

    @pytest.mark.asyncio
    async def test_breaker_async_concurrent_access(self):
        """异步场景下熔断器应保持状态一致性"""
        config = CircuitBreakerConfig(
            failure_threshold=5,
            success_threshold=2,
            timeout_seconds=5.0,
        )
        breaker = CircuitBreaker("test_async", config)

        async def successful_coroutine(id):
            for _ in range(10):
                await breaker.call(lambda: f"async_success_{id}")
                await asyncio.sleep(0.001)
            return id

        tasks = [successful_coroutine(i) for i in range(5)]
        await asyncio.gather(*tasks)

        assert breaker.state == CircuitState.CLOSED
        assert breaker.stats.successful_calls == 50

    @pytest.mark.asyncio
    async def test_breaker_async_failure_transition(self):
        """异步场景下熔断器失败状态转换应正确"""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout_seconds=5.0,
        )
        breaker = CircuitBreaker("test_async_fail", config)

        async def failing_coroutine(id):
            for _ in range(2):
                try:
                    await breaker.call(lambda: 1 / 0)
                except (ZeroDivisionError, CircuitBreakerError):
                    pass
                await asyncio.sleep(0.001)
            return id

        tasks = [failing_coroutine(i) for i in range(3)]
        await asyncio.gather(*tasks)

        assert breaker.state == CircuitState.OPEN


class TestEvaluatorFactoryThreadSafety:
    """评估器工厂线程安全测试"""

    def test_factory_register_thread_safe(self):
        """工厂注册应线程安全"""
        registered_names = []
        lock = threading.Lock()

        def register_evaluator(id):
            name = f"test_concurrent_{id}"

            @EvaluatorFactory.register(name)
            class TestConcurrentEvaluator(BaseEvaluator):
                def _do_evaluate(self, request):
                    from src.schemas.evaluation import DomainResponse

                    return DomainResponse(is_valid=True, score=1.0)

            with lock:
                registered_names.append(name)

        threads = []
        for i in range(10):
            t = threading.Thread(target=register_evaluator, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        evaluators = EvaluatorFactory.list_evaluators()
        for name in registered_names:
            assert name in evaluators

    def test_factory_get_thread_safe(self):
        """工厂获取评估器应线程安全"""
        instances = []
        lock = threading.Lock()

        @EvaluatorFactory.register("test_thread_safe_eval")
        class TestThreadSafeEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                from src.schemas.evaluation import DomainResponse

                return DomainResponse(is_valid=True, score=1.0)

        def get_evaluator(id):
            evaluator = EvaluatorFactory.get("test_thread_safe_eval")
            with lock:
                instances.append(evaluator)

        threads = []
        for i in range(10):
            t = threading.Thread(target=get_evaluator, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(instances) == 10
        assert all(isinstance(e, TestThreadSafeEvaluator) for e in instances)
