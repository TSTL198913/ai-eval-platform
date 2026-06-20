"""评估器与分布式组件集成测试"""

from unittest.mock import MagicMock

import pytest

from src.distributed.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitState,
)
from src.distributed.idempotency import IdempotencyChecker
from src.distributed.lock import DistributedLock, LockState
from src.distributed.rate_limiter import RateLimiter, RateLimitStrategy, TokenBucket
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.schemas.evaluation import EvaluationSchema


class TestEvaluatorWithCircuitBreaker:
    """评估器与熔断器集成测试"""

    @pytest.fixture
    def evaluator(self):
        return EvaluatorFactory.get("general")

    @pytest.fixture
    def breaker(self):
        return CircuitBreaker("evaluator-breaker", config=CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout_seconds=10.0,
        ))

    @pytest.mark.asyncio
    async def test_evaluator_with_circuit_breaker(self, evaluator, breaker):
        """评估器应能与熔断器配合使用"""
        request = EvaluationSchema(
            id="cb-test-001",
            type="general",
            payload={
                "user_input": "测试问题",
                "model_output": "测试回答",
                "expected_output": "期望回答",
            },
        )

        result = await breaker.call(lambda: evaluator.evaluate(request))
        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_circuit_breaker_protects_evaluator(self, breaker):
        """熔断器应保护评估器"""
        failing_evaluator = MagicMock()
        failing_evaluator.evaluate = MagicMock(side_effect=Exception("Service unavailable"))

        for _ in range(3):
            with pytest.raises(Exception):
                await breaker.call(lambda: failing_evaluator.evaluate())

        assert breaker.state == CircuitState.OPEN

        with pytest.raises(CircuitBreakerError):
            await breaker.call(lambda: failing_evaluator.evaluate())

    @pytest.mark.asyncio
    async def test_circuit_breaker_resets_after_success(self, breaker):
        """熔断器应在成功后重置"""
        counter = {"value": 0}

        def flaky_service():
            counter["value"] += 1
            if counter["value"] <= 3:
                raise Exception("Transient failure")
            return "success"

        for _ in range(3):
            with pytest.raises(Exception):
                await breaker.call(flaky_service)

        assert breaker.state == CircuitState.OPEN

        breaker.reset()
        assert breaker.state == CircuitState.CLOSED

        result = await breaker.call(flaky_service)
        assert result == "success"


class TestEvaluatorWithIdempotency:
    """评估器与幂等性集成测试"""

    @pytest.fixture
    def evaluator(self):
        return EvaluatorFactory.get("general")

    @pytest.fixture
    def mock_redis(self):
        mock = MagicMock()
        mock.exists = MagicMock(return_value=0)
        mock.setex = MagicMock()
        mock.set = MagicMock()
        mock.get = MagicMock(return_value=None)
        mock.delete = MagicMock()
        return mock

    def test_idempotent_evaluation(self, evaluator, mock_redis):
        """相同请求应返回相同结果"""
        checker = IdempotencyChecker(mock_redis)

        request = EvaluationSchema(
            id="idempotent-test-001",
            type="general",
            payload={
                "user_input": "什么是人工智能？",
                "model_output": "AI是计算机科学",
                "expected_output": "人工智能是计算机科学的分支",
            },
        )

        if checker.check("eval-001"):
            result1 = evaluator.evaluate(request)
            checker.mark_processed("eval-001", result1.score)

        mock_redis.exists = MagicMock(return_value=1)
        assert checker.check("eval-001") is False

    def test_idempotency_with_processing_state(self, evaluator, mock_redis):
        """处理中的请求应被拒绝"""
        checker = IdempotencyChecker(mock_redis)
        checker.mark_processing("eval-processing")

        mock_redis.exists = MagicMock(return_value=1)
        assert checker.check("eval-processing") is False

    def test_idempotency_clear(self, evaluator, mock_redis):
        """应能清除幂等性记录"""
        checker = IdempotencyChecker(mock_redis)
        checker.mark_processed("eval-to-clear", "result")

        result = checker.clear("eval-to-clear")
        assert result is True
        mock_redis.delete.assert_called_once()


class TestEvaluatorWithLock:
    """评估器与分布式锁集成测试"""

    @pytest.fixture
    def evaluator(self):
        return EvaluatorFactory.get("general")

    @pytest.fixture
    def mock_redis(self):
        mock = MagicMock()
        mock.set = MagicMock(return_value=True)
        mock.eval = MagicMock(return_value=1)
        return mock

    def test_evaluation_with_lock(self, evaluator, mock_redis):
        """评估应能在锁保护下执行"""
        lock = DistributedLock(mock_redis, "eval-lock")

        request = EvaluationSchema(
            id="lock-test-001",
            type="general",
            payload={
                "user_input": "测试",
                "model_output": "回答",
            },
        )

        with lock:
            result = evaluator.evaluate(request)
            assert result.is_valid is True

    def test_lock_prevents_concurrent_access(self, evaluator, mock_redis):
        """锁应防止并发访问"""
        mock_redis.set = MagicMock(side_effect=[True, False])

        lock1 = DistributedLock(mock_redis, "concurrent-lock")
        lock2 = DistributedLock(mock_redis, "concurrent-lock", retry_times=1)

        result1 = lock1.acquire()
        result2 = lock2.acquire()

        assert result1.state == LockState.ACQUIRED
        assert result2.state == LockState.NOT_ACQUIRED


class TestEvaluatorWithRateLimiter:
    """评估器与速率限制器集成测试"""

    @pytest.fixture
    def evaluator(self):
        return EvaluatorFactory.get("general")

    @pytest.fixture
    def mock_redis(self):
        mock = MagicMock()
        mock.register_script = MagicMock(return_value=MagicMock(return_value=[1, 99]))
        return mock

    def test_evaluation_with_rate_limit(self, evaluator, mock_redis):
        """评估应受速率限制保护"""
        limiter = RateLimiter(mock_redis, strategy=RateLimitStrategy.TOKEN_BUCKET)
        bucket = limiter.create_limiter("eval-rate")

        request = EvaluationSchema(
            id="rate-limit-test",
            type="general",
            payload={"user_input": "test"},
        )

        for _ in range(5):
            result = bucket.allow()
            assert result.allowed is True
            evaluator.evaluate(request)

    def test_rate_limiter_blocks_when_exhausted(self, mock_redis):
        """限流器应在令牌耗尽时阻止请求"""
        mock_redis.register_script = MagicMock(return_value=MagicMock(return_value=[0, 0]))
        bucket = TokenBucket(mock_redis, "exhausted-bucket")

        result = bucket.allow()
        assert result.allowed is False
        assert result.retry_after_ms is not None

    def test_multi_dimension_rate_limit(self, mock_redis):
        """多维度限流应正确工作"""
        from src.distributed.rate_limiter import MultiDimensionRateLimiter

        mock_redis.register_script = MagicMock(return_value=MagicMock(return_value=[1, 99]))
        multi_limiter = MultiDimensionRateLimiter(mock_redis)

        allowed, failed_result = multi_limiter.is_allowed(
            user_id="user123",
            api_key="api_key_abc",
            ip="192.168.1.1",
        )

        assert allowed is True


class TestFullIntegration:
    """完整集成测试"""

    @pytest.fixture
    def evaluator(self):
        return EvaluatorFactory.get("general")

    @pytest.fixture
    def mock_redis(self):
        mock = MagicMock()
        mock.set = MagicMock(return_value=True)
        mock.eval = MagicMock(return_value=1)
        mock.exists = MagicMock(return_value=0)
        mock.setex = MagicMock()
        mock.register_script = MagicMock(return_value=MagicMock(return_value=[1, 99]))
        return mock

    @pytest.mark.asyncio
    async def test_full_pipeline(self, evaluator, mock_redis):
        """完整评估管道"""
        breaker = CircuitBreaker("full-pipeline", config=CircuitBreakerConfig(
            failure_threshold=5,
            success_threshold=2,
            timeout_seconds=30.0,
        ))
        checker = IdempotencyChecker(mock_redis)
        lock = DistributedLock(mock_redis, "full-pipeline-lock")
        limiter = RateLimiter(mock_redis)
        bucket = limiter.create_limiter("full-pipeline-rate")

        request = EvaluationSchema(
            id="full-integration-test",
            type="general",
            payload={
                "user_input": "什么是机器学习？",
                "model_output": "机器学习是AI的分支",
                "expected_output": "机器学习是一种让计算机从数据中学习的技术",
            },
        )

        with lock:
            rate_result = bucket.allow()
            assert rate_result.allowed is True

            if checker.check("full-pipeline-id"):
                result = await breaker.call(lambda: evaluator.evaluate(request))
                checker.mark_processed("full-pipeline-id", result.score)

        assert result.is_valid is True
        assert result.score >= 0.0

    @pytest.mark.asyncio
    async def test_pipeline_failure_recovery(self, mock_redis):
        """管道故障恢复测试"""
        failing_evaluator = MagicMock()
        failing_evaluator.evaluate = MagicMock(side_effect=Exception("Temporary failure"))

        breaker = CircuitBreaker("recovery-test", config=CircuitBreakerConfig(
            failure_threshold=2,
            success_threshold=1,
            timeout_seconds=10.0,
        ))
        checker = IdempotencyChecker(mock_redis)
        lock = DistributedLock(mock_redis, "recovery-lock")
        limiter = RateLimiter(mock_redis)
        bucket = limiter.create_limiter("recovery-rate")

        request = EvaluationSchema(
            id="recovery-test-request",
            type="general",
            payload={"user_input": "test"},
        )

        with lock:
            rate_result = bucket.allow()
            assert rate_result.allowed is True

            if checker.check("recovery-id"):
                for _ in range(2):
                    with pytest.raises(Exception):
                        await breaker.call(lambda: failing_evaluator.evaluate(request))

                assert breaker.state == CircuitState.OPEN

                failing_evaluator.evaluate = MagicMock(return_value=MagicMock(is_valid=True, score=0.8))

                breaker.reset()
                result = await breaker.call(lambda: failing_evaluator.evaluate(request))
                assert result.is_valid is True
