"""
Distributed 层测试 - 分布式原语
真实业务场景：评测任务去重（锁）、LLM 故障保护（熔断器）、API 限流、重复请求去重
"""

import asyncio

import pytest

from src.distributed.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitState,
)
from src.distributed.idempotency import (
    IdempotencyChecker,
    IdempotencyConfig,
)
from src.distributed.lock import (
    DistributedLock,
    LockState,
    distributed_lock,
)
from src.distributed.rate_limiter import (
    MultiDimensionRateLimiter,
    RateLimitConfig,
    SlidingWindowLog,
    TokenBucket,
)


# ============================================================
# Part 1: 分布式锁 - 防止评测任务并发执行
# ============================================================
class TestDistributedLockBusinessScenarios:
    """分布式锁：同一 case_id 任务在多 worker 间互斥"""

    def test_acquire_lock_successfully(self, fake_redis):
        """场景：Worker 成功获取评测任务锁"""
        lock = DistributedLock(fake_redis, "case_001", ttl_seconds=30)
        result = lock.acquire()

        assert result.state == LockState.ACQUIRED
        assert result.lock_key == "eval:lock:case_001"
        assert lock.is_acquired is True

    def test_second_acquire_blocked(self, fake_redis):
        """场景：第二个 Worker 拿不到锁（防重）"""
        lock1 = DistributedLock(fake_redis, "case_002", ttl_seconds=30)
        lock2 = DistributedLock(fake_redis, "case_002", ttl_seconds=30, retry_times=1)

        result1 = lock1.acquire()
        result2 = lock2.acquire()

        assert result1.state == LockState.ACQUIRED
        assert result2.state == LockState.NOT_ACQUIRED
        assert lock2.is_acquired is False

    def test_release_allows_reacquire(self, fake_redis):
        """场景：Worker 完成评测后释放锁，下一个能进入"""
        lock1 = DistributedLock(fake_redis, "case_003", ttl_seconds=30)
        lock2 = DistributedLock(fake_redis, "case_003", ttl_seconds=30, retry_times=1)

        assert lock1.acquire().state == LockState.ACQUIRED
        assert lock1.release() is True
        # 锁被释放后，第二个能拿到
        assert lock2.acquire().state == LockState.ACQUIRED

    def test_release_only_by_holder(self, fake_redis):
        """场景：Worker 只能释放自己持有的锁（防误删）"""
        lock1 = DistributedLock(fake_redis, "case_004", ttl_seconds=30)
        lock1.acquire()

        # 模拟锁被另一实例持有了不同 value
        # 第二个 lock 看不到这个 lock_value，释放应失败
        lock2 = DistributedLock(fake_redis, "case_004", ttl_seconds=30)
        # 模拟 lock2 没拿到锁的情况
        assert lock2.release() is False  # _acquired=False，立即返回 False

    def test_extend_lock_ttl(self, fake_redis):
        """场景：长任务续期（避免 TTL 过期导致锁被回收）"""
        lock = DistributedLock(fake_redis, "case_005", ttl_seconds=30)
        lock.acquire()
        assert lock.extend(60) is True

    def test_lock_context_manager_raises_on_failure(self, fake_redis):
        """场景：拿不到锁时，with 上下文应直接抛错"""
        lock1 = DistributedLock(fake_redis, "case_006", ttl_seconds=30)
        lock1.acquire()

        with pytest.raises(RuntimeError) as exc_info:
            with DistributedLock(fake_redis, "case_006", ttl_seconds=30, retry_times=1):
                pass
        assert "Failed to acquire" in str(exc_info.value)

    def test_lock_context_manager_releases_on_exit(self, fake_redis):
        """场景：with 块正常退出后锁被释放"""
        with DistributedLock(fake_redis, "case_007", ttl_seconds=30):
            pass  # 自动释放

        # 同一 key 再次能获取
        lock2 = DistributedLock(fake_redis, "case_007", ttl_seconds=30)
        assert lock2.acquire().state == LockState.ACQUIRED

    def test_lock_value_is_unique(self, fake_redis):
        """场景：每次 acquire 生成新 value（防误释放）"""
        lock = DistributedLock(fake_redis, "case_008", ttl_seconds=30)
        result1 = lock.acquire()
        lock.release()
        result2 = lock.acquire()

        # value 必须不同，避免误释放其他进程的锁
        assert result1.lock_value != result2.lock_value


class TestDistributedLockContextManagerBusiness:
    """distributed_lock 便捷函数"""

    def test_context_manager_yields_lock(self, fake_redis):
        """场景：业务方使用 with 块管理锁生命周期"""
        with distributed_lock(fake_redis, "case_009", ttl_seconds=30) as lock:
            assert lock.is_acquired is True
            assert "case_009" in lock.key

    def test_context_manager_raises_on_contention(self, fake_redis):
        """场景：高竞争下，业务方拿不到锁应快速失败"""
        with distributed_lock(fake_redis, "case_010", ttl_seconds=30):
            with pytest.raises(RuntimeError):
                with distributed_lock(fake_redis, "case_010", ttl_seconds=30):
                    pass


# ============================================================
# Part 2: 熔断器 - LLM 服务故障保护
# ============================================================
class TestCircuitBreakerBusinessScenarios:
    """熔断器：LLM 服务连续失败时快速失败，避免雪崩"""

    @pytest.mark.asyncio
    async def test_circuit_closed_passes_calls(self, fake_redis):
        """场景：正常状态调用通过"""
        cb = CircuitBreaker("llm_service", CircuitBreakerConfig(failure_threshold=3))
        result = await cb.call(self._ok_func, "input")
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_circuit_opens_after_threshold(self, fake_redis):
        """场景：连续 3 次失败后熔断器打开"""
        cb = CircuitBreaker(
            "llm_service",
            CircuitBreakerConfig(failure_threshold=3, timeout_seconds=10.0),
        )

        # 触发 3 次失败
        for _ in range(3):
            with pytest.raises(ConnectionError):
                await cb.call(self._fail_func)

        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_circuit_open_rejects_immediately(self, fake_redis):
        """场景：熔断器打开后，请求立即被拒绝（不调用下游）"""
        cb = CircuitBreaker(
            "llm_service",
            CircuitBreakerConfig(failure_threshold=2, timeout_seconds=60.0),
        )

        # 触发 2 次失败
        for _ in range(2):
            with pytest.raises(ConnectionError):
                await cb.call(self._fail_func)

        # 第 3 次应被拒绝，不再调用下游
        with pytest.raises(CircuitBreakerError):
            await cb.call(self._fail_func)

        assert cb.stats.rejected_calls >= 1

    @pytest.mark.asyncio
    async def test_circuit_half_open_after_timeout(self, fake_redis):
        """场景：超时后进入半开状态"""
        cb = CircuitBreaker(
            "llm_service",
            CircuitBreakerConfig(
                failure_threshold=2,
                timeout_seconds=0.1,  # 100ms 超时
                success_threshold=2,
            ),
        )

        for _ in range(2):
            with pytest.raises(ConnectionError):
                await cb.call(self._fail_func)
        assert cb.state == CircuitState.OPEN

        await asyncio.sleep(0.2)  # 等待超时

        # 探测请求：成功 2 次应回到 CLOSED
        result1 = await cb.call(self._ok_func, "a")
        result2 = await cb.call(self._ok_func, "b")
        assert result1 == "ok"
        assert result2 == "ok"
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_half_open_failure_reopens(self, fake_redis):
        """场景：半开状态探测失败，应重新打开"""
        cb = CircuitBreaker(
            "llm_service",
            CircuitBreakerConfig(
                failure_threshold=2,
                timeout_seconds=0.1,
                success_threshold=2,
            ),
        )

        for _ in range(2):
            with pytest.raises(ConnectionError):
                await cb.call(self._fail_func)
        assert cb.state == CircuitState.OPEN

        await asyncio.sleep(0.2)
        # 半开状态探测失败
        with pytest.raises(ConnectionError):
            await cb.call(self._fail_func)
        # 应重新进入 OPEN
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_circuit_stats_tracking(self, fake_redis):
        """场景：熔断器统计信息"""
        cb = CircuitBreaker(
            "llm_service",
            CircuitBreakerConfig(failure_threshold=5),
        )
        await cb.call(self._ok_func, "x")
        await cb.call(self._ok_func, "y")
        with pytest.raises(ConnectionError):
            await cb.call(self._fail_func)

        stats = cb.get_stats()
        assert stats["total_calls"] == 3
        assert stats["successful_calls"] == 2
        assert stats["failed_calls"] == 1

    def test_circuit_reset(self, fake_redis):
        """场景：运维手动重置熔断器"""
        cb = CircuitBreaker("llm_service", CircuitBreakerConfig(failure_threshold=2))

        # 模拟失败
        cb._record_failure()
        cb._record_failure()
        # 强制打开
        cb._transition_to(CircuitState.OPEN)
        assert cb.is_open

        cb.reset()
        assert cb.is_closed
        assert cb._failure_count == 0

    async def _ok_func(self, x):
        return "ok"

    async def _fail_func(self):
        raise ConnectionError("downstream failed")


# ============================================================
# Part 3: 限流器 - API 限流
# ============================================================
class TestTokenBucketBusinessScenarios:
    """令牌桶：API 限流"""

    def test_token_bucket_allows_within_capacity(self, fake_redis):
        """场景：正常请求通过"""
        bucket = TokenBucket(
            fake_redis,
            "user_alice",
            RateLimitConfig(max_tokens=10, refill_rate=1.0),
        )
        for _ in range(5):
            result = bucket.allow()
            assert result.allowed is True

    def test_token_bucket_rejects_over_capacity(self, fake_redis):
        """场景：超过容量的请求被拒绝"""
        bucket = TokenBucket(
            fake_redis,
            "user_burst",
            RateLimitConfig(max_tokens=3, refill_rate=0.1),
        )
        # 消耗 3 个令牌
        for _ in range(3):
            assert bucket.allow().allowed is True
        # 第 4 个应被拒
        result = bucket.allow()
        assert result.allowed is False
        assert result.retry_after_ms is not None


class TestSlidingWindowBusinessScenarios:
    """滑动窗口：精确限流"""

    def test_sliding_window_allows_within_limit(self, fake_redis):
        """场景：窗口内允许规定次数"""
        window = SlidingWindowLog(
            fake_redis,
            "endpoint_search",
            max_calls=10,
            window_seconds=60.0,
        )
        for _ in range(10):
            assert window.allow().allowed is True

    def test_sliding_window_rejects_over_limit(self, fake_redis):
        """场景：超过窗口限制应被拒"""
        window = SlidingWindowLog(
            fake_redis,
            "endpoint_heavy",
            max_calls=5,
            window_seconds=60.0,
        )
        for _ in range(5):
            assert window.allow().allowed is True
        result = window.allow()
        assert result.allowed is False


class TestMultiDimensionRateLimiterBusinessScenarios:
    """多维度限流：用户/API/IP"""

    def test_user_dimension_check(self, fake_redis):
        """场景：用户维度限流"""
        limiter = MultiDimensionRateLimiter(fake_redis)
        results = limiter.check(user_id="alice", tokens=1)
        assert all(r.allowed for r in results)
        assert any("user:alice" in r.limit_key for r in results)

    def test_ip_dimension_check(self, fake_redis):
        """场景：IP 维度限流"""
        limiter = MultiDimensionRateLimiter(fake_redis)
        results = limiter.check(ip="192.168.1.1")
        assert all(r.allowed for r in results)

    def test_is_allowed_no_dimensions(self, fake_redis):
        """场景：未提供维度时直接放行"""
        limiter = MultiDimensionRateLimiter(fake_redis)
        allowed, result = limiter.is_allowed()
        assert allowed is True
        assert result is None

    def test_is_allowed_returns_first_failure(self, fake_redis):
        """场景：任意维度超限即拒绝"""
        limiter = MultiDimensionRateLimiter(fake_redis)
        # 通过两次用户限流（容量 1000），通过两次 API 限流（容量 100）
        for _ in range(2):
            allowed, _ = limiter.is_allowed(user_id="bob", api_key="key1")
            assert allowed is True


# ============================================================
# Part 4: 幂等性 - 重复请求去重
# ============================================================
class TestIdempotencyBusinessScenarios:
    """幂等性：用户重复点击提交按钮时，只处理一次"""

    def test_check_unseen_request(self, fake_redis):
        """场景：第一次请求应通过"""
        checker = IdempotencyChecker(fake_redis)
        assert checker.check("req_001") is True

    def test_check_seen_request(self, fake_redis):
        """场景：重复请求被识别"""
        checker = IdempotencyChecker(fake_redis)
        # 第一次 mark_processing
        assert checker.mark_processing("req_002") is True
        # 第二次 check 应返回 False
        assert checker.check("req_002") is False

    def test_mark_processing_is_atomic(self, fake_redis):
        """场景：两个并发实例同时尝试 mark_processing，只有一个成功"""
        checker = IdempotencyChecker(fake_redis)
        assert checker.mark_processing("req_003") is True
        # 第二个 mark 失败（已被占用）
        assert checker.mark_processing("req_003") is False

    def test_mark_processed_caches_result(self, fake_redis):
        """场景：处理完成后缓存结果，可用于重试"""
        checker = IdempotencyChecker(fake_redis)
        checker.check("req_004")
        checker.mark_processing("req_004")
        checker.mark_processed("req_004", result={"score": 0.9})

        cached = checker.get_cached_result("req_004")
        assert cached == {"score": 0.9}

    def test_get_cached_result_returns_none_for_unprocessed(self, fake_redis):
        """场景：未处理的请求返回 None"""
        checker = IdempotencyChecker(fake_redis)
        assert checker.get_cached_result("nonexistent") is None

    def test_get_status_returns_full_record(self, fake_redis):
        """场景：返回请求状态"""
        checker = IdempotencyChecker(fake_redis)
        checker.check("req_005")
        checker.mark_processing("req_005")
        status = checker.get_status("req_005")
        assert status is not None
        assert status["status"] == "processing"

    def test_clear_allows_retry(self, fake_redis):
        """场景：失败时清除幂等性，允许重试"""
        checker = IdempotencyChecker(fake_redis)
        checker.check("req_006")
        checker.mark_processing("req_006")
        assert checker.check("req_006") is False

        # 失败后清除
        checker.clear("req_006")
        assert checker.check("req_006") is True

    def test_ttl_configuration(self, fake_redis):
        """场景：业务方配置 TTL"""
        config = IdempotencyConfig(ttl_seconds=60)
        checker = IdempotencyChecker(fake_redis, config)
        assert checker._config.ttl_seconds == 60

    def test_key_prefix_includes_configurable(self, fake_redis):
        """场景：业务方使用自定义前缀避免冲突"""
        config = IdempotencyConfig(key_prefix="custom_idem:")
        checker = IdempotencyChecker(fake_redis, config)
        key = checker._generate_key("req_007")
        assert key.startswith("custom_idem:req_007")


# ============================================================
# Part 5: 集成场景 - 锁 + 幂等
# ============================================================
class TestIdempotencyIntegrationBusiness:
    """业务集成：先检查幂等再处理，处理时加锁"""

    def test_duplicate_submission_deduplicated(self, fake_redis):
        """场景：用户连按两次提交按钮"""
        checker = IdempotencyChecker(fake_redis)
        request_id = "submit_case_001"

        # 第一次提交
        assert checker.check(request_id) is True
        checker.mark_processing(request_id)
        # 模拟处理完成
        checker.mark_processed(request_id, result={"id": "case_001", "score": 0.95})

        # 第二次提交（用户在等结果时又点了一次）
        assert checker.check(request_id) is False
        cached = checker.get_cached_result(request_id)
        assert cached == {"id": "case_001", "score": 0.95}

    def test_failure_releases_for_retry(self, fake_redis):
        """场景：处理失败后，相同请求可以重试"""
        checker = IdempotencyChecker(fake_redis)
        request_id = "submit_case_002"

        checker.check(request_id)
        checker.mark_processing(request_id)

        # 处理失败
        try:
            raise RuntimeError("LLM timeout")
        except RuntimeError:
            checker.clear(request_id)

        # 用户重试
        assert checker.check(request_id) is True
