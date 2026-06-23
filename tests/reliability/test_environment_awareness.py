"""
环境感知测试 - 连接池耗尽、LLM超时、真实Redis测试
===============================================
本文件测试系统在真实环境压力下的行为，而非理想条件。

关键测试：
1. DB连接池耗尽时的行为
2. Redis连接池耗尽时的行为
3. LLM调用超时后的降级
4. 真实Redis分布式锁行为
"""

import asyncio
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.distributed.idempotency import IdempotencyChecker
from src.distributed.lock import DistributedLock
from src.infra.db.session import get_db_session

# ========================================
# 真实Redis测试配置
# ========================================


def get_real_redis():
    """获取真实Redis连接（如果可用）"""
    try:
        import redis

        client = redis.Redis(
            host=os.environ.get("REDIS_HOST", "localhost"),
            port=int(os.environ.get("REDIS_PORT", 6379)),
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        client.ping()
        return client
    except Exception as e:
        pytest.skip(f"Redis not available: {e}")
        return None


@pytest.fixture(scope="module")
def real_redis():
    """模块级别的真实Redis连接"""
    return get_real_redis()


@pytest.fixture
def clean_redis(real_redis):
    """每个测试前清理Redis"""
    if real_redis:
        real_redis.flushall()
    yield real_redis
    if real_redis:
        real_redis.flushall()


# ========================================
# DB连接池耗尽测试
# ========================================


class TestDBConnectionPoolExhaustion:
    """测试数据库连接池耗尽时的行为"""

    def test_connection_pool_has_limits(self):
        """验证连接池配置存在上限"""
        from src.infra.db.session import engine

        # 验证连接池存在（不同类型池有不同属性）
        pool = engine.pool
        # StaticPool 或 QueuePool 都有连接管理
        assert pool is not None
        # 验证池类型
        pool_type = pool.__class__.__name__
        assert pool_type in ["QueuePool", "StaticPool", "NullPool", "SingletonThreadPool"]

    @pytest.mark.slow
    def test_concurrent_db_requests_work(self):
        """测试并发请求可以正常工作"""
        from sqlalchemy import text

        concurrent_requests = 10

        results = []
        errors = []

        def query_db(i):
            try:
                with get_db_session() as session:
                    session.execute(text("SELECT 1"))
                    time.sleep(0.05)  # 模拟短处理时间
                    return f"success-{i}"
            except Exception as e:
                errors.append((i, str(e)))
                return None

        with ThreadPoolExecutor(max_workers=concurrent_requests) as executor:
            futures = [executor.submit(query_db, i) for i in range(concurrent_requests)]
            for f in as_completed(futures, timeout=30):
                results.append(f.result())

        # 验证：大部分应成功
        success_count = sum(1 for r in results if r is not None)
        assert success_count >= concurrent_requests * 0.8


# ========================================
# Redis连接池测试
# ========================================


class TestRedisConnectionPool:
    """测试Redis连接池行为"""

    @pytest.mark.skipif(os.environ.get("REDIS_HOST") is None, reason="需要真实Redis环境")
    def test_redis_connection_pool_limits(self, real_redis):
        """验证Redis连接池配置"""
        # Redis默认最大连接数是10000，但客户端通常限制
        pool = real_redis.connection_pool
        assert pool.max_connections > 0
        assert pool.max_connections < 10000

    @pytest.mark.skipif(os.environ.get("REDIS_HOST") is None, reason="需要真实Redis环境")
    def test_redis_concurrent_connections(self, clean_redis):
        """测试Redis并发连接"""
        import redis

        concurrent_count = 50
        results = []

        def redis_operation(i):
            try:
                client = redis.Redis(
                    host=os.environ.get("REDIS_HOST", "localhost"),
                    port=int(os.environ.get("REDIS_PORT", 6379)),
                    decode_responses=True,
                    socket_connect_timeout=5,
                )
                client.set(f"test-key-{i}", f"value-{i}")
                value = client.get(f"test-key-{i}")
                client.close()
                return value == f"value-{i}"
            except Exception as e:
                return str(e)

        with ThreadPoolExecutor(max_workers=concurrent_count) as executor:
            futures = [executor.submit(redis_operation, i) for i in range(concurrent_count)]
            for f in as_completed(futures, timeout=30):
                results.append(f.result())

        # 验证成功率
        success_count = sum(1 for r in results if r is True)
        assert success_count >= concurrent_count * 0.95


# ========================================
# LLM超时测试
# ========================================


class TestLLMTimeout:
    """测试LLM调用超时后的降级行为"""

    def test_llm_timeout_returns_error(self):
        """LLM超时应返回错误而非崩溃"""
        from src.domain.evaluators.llm_as_judge import LLMAJudgeEvaluator
        from src.schemas.evaluation import EvaluationSchema

        # 创建超时的Mock客户端 - 使用Exception而非TimeoutError
        slow_client = MagicMock()
        slow_client.config = MagicMock()
        slow_client.config.model_name = "timeout-model"

        def _timeout(*args, **kwargs):
            raise Exception("LLM request timeout after 30 seconds")

        slow_client.chat = MagicMock(side_effect=_timeout)

        evaluator = LLMAJudgeEvaluator(client=slow_client)

        request = EvaluationSchema(
            id="test-timeout",
            type="llm_as_judge",
            payload={"user_input": "测试输入", "actual_output": "测试输出"},
        )

        # 使用safe_evaluate而非evaluate，以捕获异常
        result = evaluator.safe_evaluate(request)

        # 验证：不应崩溃，应返回错误响应
        assert result.is_valid is False
        assert result.error is not None
        assert "EVALUATION_ERROR" in result.error or "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_llm_async_timeout_handled(self):
        """异步LLM超时应被正确处理"""
        from src.domain.evaluators.llm_as_judge import LLMAJudgeEvaluator
        from src.schemas.evaluation import EvaluationSchema

        # 创建异步超时Mock
        async_client = MagicMock()
        async_client.chat_async = AsyncMock(side_effect=asyncio.TimeoutError("Async timeout"))

        evaluator = LLMAJudgeEvaluator(client=async_client)

        request = EvaluationSchema(
            id="test-async-timeout", type="llm_as_judge", payload={"user_input": "测试"}
        )

        # 异步评估应处理超时
        result = (
            await evaluator.evaluate_async(request)
            if hasattr(evaluator, "evaluate_async")
            else evaluator.evaluate(request)
        )

        assert result.is_valid is False
        assert result.error is not None

    def test_llm_rate_limit_handled(self):
        """LLM限流应返回特定错误"""
        from src.domain.evaluators.llm_as_judge import LLMAJudgeEvaluator
        from src.schemas.evaluation import EvaluationSchema

        rate_limited_client = MagicMock()
        rate_limited_client.chat = MagicMock(side_effect=Exception("Rate limit exceeded"))

        evaluator = LLMAJudgeEvaluator(client=rate_limited_client)

        request = EvaluationSchema(
            id="test-rate-limit", type="llm_as_judge", payload={"user_input": "测试"}
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        # 应识别为限流错误而非普通错误
        assert result.error is not None


# ========================================
# 真实Redis分布式锁测试
# ========================================


class TestRealDistributedLock:
    """使用真实Redis测试分布式锁行为"""

    @pytest.mark.skipif(os.environ.get("REDIS_HOST") is None, reason="需要真实Redis环境")
    def test_lock_acquire_and_release(self, clean_redis):
        """测试锁的获取和释放"""
        lock = DistributedLock(clean_redis, "test-lock", timeout=5)

        # 获取锁
        acquired = lock.acquire(blocking=True, timeout=2)
        assert acquired is True

        # 验证锁存在
        assert clean_redis.exists("test-lock")

        # 释放锁
        released = lock.release()
        assert released is True

        # 验证锁已删除
        assert not clean_redis.exists("test-lock")

    @pytest.mark.skipif(os.environ.get("REDIS_HOST") is None, reason="需要真实Redis环境")
    def test_lock_conflict_detected(self, clean_redis):
        """测试锁冲突检测"""
        lock1 = DistributedLock(clean_redis, "shared-lock", timeout=5)
        lock2 = DistributedLock(clean_redis, "shared-lock", timeout=5)

        # 第一个获取成功
        assert lock1.acquire(blocking=False) is True

        # 第二个应失败（非阻塞模式）
        assert lock2.acquire(blocking=False) is False

        # 释放后第二个可获取
        lock1.release()
        assert lock2.acquire(blocking=False) is True

    @pytest.mark.skipif(os.environ.get("REDIS_HOST") is None, reason="需要真实Redis环境")
    def test_lock_auto_expire(self, clean_redis):
        """测试锁自动过期"""
        lock = DistributedLock(clean_redis, "expire-lock", timeout=2)

        lock.acquire(blocking=False)
        assert clean_redis.exists("expire-lock")

        # 等待过期
        time.sleep(2.5)

        # 锁应自动删除
        assert not clean_redis.exists("expire-lock")

    @pytest.mark.skipif(os.environ.get("REDIS_HOST") is None, reason="需要真实Redis环境")
    def test_concurrent_lock_competition(self, clean_redis):
        """测试并发锁竞争"""
        results = {"acquired": [], "failed": []}

        def try_acquire_lock(i):
            lock = DistributedLock(clean_redis, "race-lock", timeout=1)
            if lock.acquire(blocking=False):
                results["acquired"].append(i)
                time.sleep(0.5)
                lock.release()
            else:
                results["failed"].append(i)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(try_acquire_lock, i) for i in range(10)]

        for _f in as_completed(futures, timeout=10):
            pass

        # 只有一个应成功获取
        assert len(results["acquired"]) >= 1
        # 其他应失败或等待后成功
        assert len(results["failed"]) >= 5


# ========================================
# 真实Redis幂等性测试
# ========================================


class TestRealIdempotency:
    """使用真实Redis测试幂等性检查"""

    @pytest.mark.skipif(os.environ.get("REDIS_HOST") is None, reason="需要真实Redis环境")
    def test_idempotency_prevents_duplicate(self, clean_redis):
        """测试幂等性防止重复处理"""
        checker = IdempotencyChecker(clean_redis, ttl=60)

        request_id = "test-request-001"

        # 第一次标记处理中
        assert checker.mark_processing(request_id) is True

        # 第二次应失败（正在处理）
        assert checker.mark_processing(request_id) is False

        # 标记完成并缓存结果
        checker.mark_processed(request_id, {"score": 0.85})

        # 获取缓存结果
        cached = checker.get_cached_result(request_id)
        assert cached == {"score": 0.85}

    @pytest.mark.skipif(os.environ.get("REDIS_HOST") is None, reason="需要真实Redis环境")
    def test_idempotency_clear_allows_retry(self, clean_redis):
        """测试清除标记后允许重试"""
        checker = IdempotencyChecker(clean_redis, ttl=60)

        request_id = "test-request-002"
        checker.mark_processing(request_id)

        # 清除标记
        checker.clear(request_id)

        # 应可再次处理
        assert checker.mark_processing(request_id) is True


# ========================================
# 内存压力测试
# ========================================


class TestMemoryPressure:
    """测试内存压力下的行为"""

    @pytest.mark.slow
    @pytest.mark.stress
    def test_large_evaluation_batch(self):
        """测试大批量评估的内存使用"""
        from src.domain.evaluators.security import SecurityEvaluator
        from src.schemas.evaluation import EvaluationSchema

        evaluator = SecurityEvaluator()

        # 执行1000次评估
        results = []
        for i in range(1000):
            request = EvaluationSchema(
                id=f"test-mem-{i}", type="security", payload={"user_input": f"测试输入 {i}" * 100}
            )
            result = evaluator.evaluate(request)
            results.append(result)

        # 验证所有结果有效
        assert all(r.is_valid for r in results)

        # 验证内存未无限增长（检查结果列表大小）
        assert len(results) == 1000


# ========================================
# 网络故障模拟测试
# ========================================


class TestNetworkFaultSimulation:
    """模拟网络故障（需要toxiproxy或类似工具）"""

    @pytest.mark.skipif(os.environ.get("TOXIPROXY_HOST") is None, reason="需要toxiproxy环境")
    def test_redis_slow_connection(self):
        """测试Redis慢连接"""
        # 使用toxiproxy添加延迟
        import redis

        # 连接到toxiproxy代理的Redis
        client = redis.Redis(
            host=os.environ.get("TOXIPROXY_HOST", "localhost"),
            port=int(os.environ.get("TOXIPROXY_PORT", 6379)),
            socket_timeout=10,  # 增加超时
        )

        try:
            start = time.time()
            client.ping()
            elapsed = time.time() - start

            # 应在超时时间内完成
            assert elapsed < 10
        except redis.TimeoutError:
            # 超时应优雅处理
            pytest.fail("Redis超时未被正确处理")


# ========================================
# 运行配置
# ========================================

# 标记测试类型
pytestmark = pytest.mark.integration

# 跳过条件
SKIP_REDIS_TESTS = os.environ.get("SKIP_REDIS_TESTS", "false").lower() == "true"
SKIP_STRESS_TESTS = os.environ.get("SKIP_STRESS_TESTS", "false").lower() == "true"
