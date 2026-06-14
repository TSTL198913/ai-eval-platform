"""补充测试 distributed/rate_limiter.py - 限流器"""

from unittest.mock import Mock

import pytest
import redis

from src.distributed.rate_limiter import (
    MultiDimensionRateLimiter,
    RateLimitConfig,
    RateLimitResult,
    RateLimitStrategy,
    SlidingWindowLog,
    TokenBucket,
    rate_limit_async,
)


class TestRateLimitConfig:
    """测试限流配置"""

    def test_default_config(self):
        config = RateLimitConfig()
        assert config.max_tokens == 100
        assert config.refill_rate == 10.0
        assert config.initial_tokens is None

    def test_custom_config(self):
        config = RateLimitConfig(max_tokens=50, refill_rate=5.0, initial_tokens=20)
        assert config.max_tokens == 50
        assert config.refill_rate == 5.0
        assert config.initial_tokens == 20


class TestRateLimitResult:
    """测试限流结果"""

    def test_allowed(self):
        result = RateLimitResult(
            allowed=True, remaining_tokens=50, retry_after_ms=None, limit_key="test"
        )
        assert result.allowed is True
        assert result.remaining_tokens == 50
        assert result.retry_after_ms is None

    def test_denied(self):
        result = RateLimitResult(
            allowed=False, remaining_tokens=0, retry_after_ms=100, limit_key="test"
        )
        assert result.allowed is False
        assert result.retry_after_ms == 100


class TestTokenBucket:
    """测试令牌桶算法"""

    @pytest.fixture
    def mock_redis(self):
        mock = Mock()
        mock.register_script.return_value = Mock()
        return mock

    @pytest.fixture
    def bucket(self, mock_redis):
        return TokenBucket(mock_redis, "test_key")

    def test_initialization(self, bucket, mock_redis):
        assert bucket.key == "ratelimit:token_bucket:test_key"
        mock_redis.register_script.assert_called_once()

    def test_allow_success(self, bucket, mock_redis):
        mock_script = Mock()
        mock_script.return_value = [1, 99]
        bucket._script = mock_script

        result = bucket.allow()
        assert result.allowed is True
        assert result.remaining_tokens == 99
        assert result.limit_key == bucket.key

    def test_allow_denied(self, bucket, mock_redis):
        mock_script = Mock()
        mock_script.return_value = [0, 0]
        bucket._script = mock_script

        result = bucket.allow()
        assert result.allowed is False
        assert result.retry_after_ms is not None
        assert result.retry_after_ms > 0

    def test_custom_config(self, mock_redis):
        config = RateLimitConfig(max_tokens=200, refill_rate=20.0)
        bucket = TokenBucket(mock_redis, "test", config)
        assert bucket.config.max_tokens == 200

    def test_allow_with_custom_tokens(self, bucket):
        """测试消耗多个令牌"""
        mock_script = Mock()
        mock_script.return_value = [1, 95]
        bucket._script = mock_script

        result = bucket.allow(tokens=5)
        assert result.allowed is True
        assert result.remaining_tokens == 95


class TestSlidingWindowLog:
    """测试滑动窗口日志算法"""

    @pytest.fixture
    def mock_redis(self):
        mock = Mock()
        mock.register_script.return_value = Mock()
        return mock

    @pytest.fixture
    def window(self, mock_redis):
        return SlidingWindowLog(mock_redis, "test", max_calls=100, window_seconds=60.0)

    def test_initialization(self, window, mock_redis):
        assert window.key == "ratelimit:sliding:test"
        assert window.max_calls == 100
        assert window.window_ms == 60000

    def test_allow_success(self, window, mock_redis):
        mock_script = Mock()
        mock_script.return_value = [1, 99]
        window._script = mock_script

        result = window.allow()
        assert result.allowed is True
        assert result.remaining_tokens == 99

    def test_allow_denied(self, window):
        """测试滑动窗口拒绝"""
        mock_script = Mock()
        mock_script.return_value = [0, 0]
        window._script = mock_script

        result = window.allow()
        assert result.allowed is False
        assert result.retry_after_ms is not None

    def test_allow_boundary(self, window):
        """测试边界条件 - 刚好达到限制"""
        mock_script = Mock()
        mock_script.return_value = [0, 0]
        window._script = mock_script

        result = window.allow()
        assert result.allowed is False


class TestRateLimitStrategy:
    """测试限流策略枚举"""

    def test_values(self):
        assert RateLimitStrategy.TOKEN_BUCKET.value == "token_bucket"
        assert RateLimitStrategy.FIXED_WINDOW.value == "fixed_window"
        assert RateLimitStrategy.SLIDING_WINDOW.value == "sliding_window"


class TestRateLimiter:
    """测试限流器工厂"""

    @pytest.fixture
    def mock_redis(self):
        mock = Mock(spec=redis.Redis)
        mock.register_script.return_value = Mock()
        return mock

    def test_create_token_bucket(self, mock_redis):
        """测试创建令牌桶限流器"""
        from src.distributed.rate_limiter import RateLimiter

        factory = RateLimiter(mock_redis, strategy=RateLimitStrategy.TOKEN_BUCKET)
        limiter = factory.create_limiter("test_key")
        assert isinstance(limiter, TokenBucket)

    def test_create_sliding_window(self, mock_redis):
        """测试创建滑动窗口限流器"""
        from src.distributed.rate_limiter import RateLimiter

        factory = RateLimiter(mock_redis, strategy=RateLimitStrategy.SLIDING_WINDOW)
        limiter = factory.create_limiter("test_key", max_calls=50, window_seconds=30.0)
        assert isinstance(limiter, SlidingWindowLog)
        assert limiter.max_calls == 50
        assert limiter.window_ms == 30000

    def test_create_with_config(self, mock_redis):
        """测试使用配置创建限流器"""
        from src.distributed.rate_limiter import RateLimiter

        factory = RateLimiter(mock_redis)
        config = RateLimitConfig(max_tokens=100, refill_rate=10.0)
        limiter = factory.create_limiter("test_key", config=config)
        assert isinstance(limiter, TokenBucket)

    def test_create_default_strategy(self, mock_redis):
        """测试默认策略"""
        from src.distributed.rate_limiter import RateLimiter

        factory = RateLimiter(mock_redis)
        limiter = factory.create_limiter("test_key")
        assert isinstance(limiter, TokenBucket)

    def test_create_unknown_strategy_fallback(self, mock_redis):
        """测试未知策略回退到令牌桶"""
        from src.distributed.rate_limiter import RateLimiter

        factory = RateLimiter(mock_redis, strategy=RateLimitStrategy.FIXED_WINDOW)
        limiter = factory.create_limiter("test_key")
        assert isinstance(limiter, TokenBucket)


class TestMultiDimensionRateLimiter:
    """测试多维度限流器"""

    @pytest.fixture
    def mock_redis(self):
        mock = Mock(spec=redis.Redis)
        mock.register_script.return_value = Mock()
        return mock

    @pytest.fixture
    def multi_limiter(self, mock_redis):
        return MultiDimensionRateLimiter(mock_redis)

    def test_check_all_allowed(self, multi_limiter):
        """测试所有维度都允许"""
        mock_script = Mock()
        mock_script.return_value = [1, 99]

        # 预创建 limiter 并替换 script
        for dim in ["user:test_user", "apikey:test_key", "ip:127.0.0.1"]:
            limiter = multi_limiter._get_limiter(
                dim, RateLimitConfig(max_tokens=100, refill_rate=10)
            )
            limiter._script = mock_script

        results = multi_limiter.check(user_id="test_user", api_key="test_key", ip="127.0.0.1")
        assert len(results) == 3
        assert all(r.allowed for r in results)

    def test_check_one_denied(self, multi_limiter):
        """测试一个维度被拒绝"""
        # 用户允许
        user_limiter = multi_limiter._get_limiter(
            "user:test_user", RateLimitConfig(max_tokens=100, refill_rate=10)
        )
        user_limiter._script = Mock(return_value=[1, 99])

        # API Key 拒绝
        api_limiter = multi_limiter._get_limiter(
            "apikey:test_key", RateLimitConfig(max_tokens=100, refill_rate=10)
        )
        api_limiter._script = Mock(return_value=[0, 0])

        results = multi_limiter.check(user_id="test_user", api_key="test_key")
        assert len(results) == 2
        assert results[0].allowed is True
        assert results[1].allowed is False

    def test_check_no_dimensions(self, multi_limiter):
        """测试无维度时返回空列表"""
        results = multi_limiter.check()
        assert results == []

    def test_is_allowed_true(self, multi_limiter):
        """测试 is_allowed 返回 True"""
        mock_script = Mock(return_value=[1, 99])
        limiter = multi_limiter._get_limiter(
            "user:test_user", RateLimitConfig(max_tokens=100, refill_rate=10)
        )
        limiter._script = mock_script

        allowed, failed = multi_limiter.is_allowed(user_id="test_user")
        assert allowed is True
        assert failed is None

    def test_is_allowed_false(self, multi_limiter):
        """测试 is_allowed 返回 False"""
        mock_script = Mock(return_value=[0, 0])
        limiter = multi_limiter._get_limiter(
            "user:test_user", RateLimitConfig(max_tokens=100, refill_rate=10)
        )
        limiter._script = mock_script

        allowed, failed = multi_limiter.is_allowed(user_id="test_user")
        assert allowed is False
        assert failed is not None
        assert failed.allowed is False

    def test_limiter_caching(self, multi_limiter):
        """测试限流器缓存"""
        limiter1 = multi_limiter._get_limiter(
            "user:same", RateLimitConfig(max_tokens=100, refill_rate=10)
        )
        limiter2 = multi_limiter._get_limiter(
            "user:same", RateLimitConfig(max_tokens=100, refill_rate=10)
        )
        assert limiter1 is limiter2


class TestRateLimitAsync:
    """测试异步限流函数"""

    @pytest.mark.asyncio
    async def test_rate_limit_async_success_first_try(self):
        """测试首次尝试成功"""
        bucket = Mock(spec=TokenBucket)
        bucket.allow.return_value = RateLimitResult(
            allowed=True, remaining_tokens=99, retry_after_ms=None, limit_key="test"
        )

        result = await rate_limit_async(bucket, tokens=1)
        assert result.allowed is True
        assert result.remaining_tokens == 99

    @pytest.mark.asyncio
    async def test_rate_limit_async_success_after_retry(self):
        """测试重试后成功"""
        bucket = Mock(spec=TokenBucket)
        bucket.allow.side_effect = [
            RateLimitResult(allowed=False, remaining_tokens=0, retry_after_ms=10, limit_key="test"),
            RateLimitResult(
                allowed=True, remaining_tokens=99, retry_after_ms=None, limit_key="test"
            ),
        ]

        result = await rate_limit_async(bucket, tokens=1, retry_delay=0.01)
        assert result.allowed is True
        assert bucket.allow.call_count == 2

    @pytest.mark.asyncio
    async def test_rate_limit_async_exhausted(self):
        """测试重试耗尽"""
        bucket = Mock(spec=TokenBucket)
        bucket.key = "test_bucket"
        bucket.allow.return_value = RateLimitResult(
            allowed=False, remaining_tokens=0, retry_after_ms=100, limit_key="test"
        )

        result = await rate_limit_async(bucket, tokens=1, max_retries=2, retry_delay=0.01)
        assert result.allowed is False
        assert bucket.allow.call_count == 2
