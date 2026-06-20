"""分布式速率限制器测试"""

from unittest.mock import MagicMock

import pytest

from src.distributed.rate_limiter import (
    RateLimitConfig,
    RateLimiter,
    RateLimitResult,
    RateLimitStrategy,
    SlidingWindowLog,
    TokenBucket,
)


class TestTokenBucketBasic:
    """令牌桶基础测试"""

    @pytest.fixture
    def mock_redis(self):
        mock = MagicMock()
        mock.register_script = MagicMock(return_value=MagicMock(return_value=[1, 99]))
        return mock

    def test_allow_success(self, mock_redis):
        bucket = TokenBucket(mock_redis, "test-bucket")
        result = bucket.allow()
        assert result.allowed is True
        assert result.remaining_tokens == 99

    def test_allow_failure(self, mock_redis):
        mock_redis.register_script = MagicMock(return_value=MagicMock(return_value=[0, 0]))
        bucket = TokenBucket(mock_redis, "test-bucket")
        result = bucket.allow()
        assert result.allowed is False
        assert result.remaining_tokens == 0
        assert result.retry_after_ms is not None

    def test_custom_config(self, mock_redis):
        config = RateLimitConfig(max_tokens=50, refill_rate=5.0)
        bucket = TokenBucket(mock_redis, "custom-bucket", config=config)
        assert bucket.config.max_tokens == 50
        assert bucket.config.refill_rate == 5.0


class TestSlidingWindowLogBasic:
    """滑动窗口日志基础测试"""

    @pytest.fixture
    def mock_redis(self):
        mock = MagicMock()
        mock.register_script = MagicMock(return_value=MagicMock(return_value=[1, 9]))
        return mock

    def test_allow_success(self, mock_redis):
        window = SlidingWindowLog(mock_redis, "test-window", max_calls=10, window_seconds=60.0)
        result = window.allow()
        assert result.allowed is True
        assert result.remaining_tokens == 9

    def test_allow_failure(self, mock_redis):
        mock_redis.register_script = MagicMock(return_value=MagicMock(return_value=[0, 0]))
        window = SlidingWindowLog(mock_redis, "test-window", max_calls=10, window_seconds=60.0)
        result = window.allow()
        assert result.allowed is False
        assert result.retry_after_ms is not None


class TestRateLimiterBasic:
    """速率限制器基础测试"""

    @pytest.fixture
    def mock_redis(self):
        mock = MagicMock()
        mock.register_script = MagicMock(return_value=MagicMock(return_value=[1, 99]))
        return mock

    def test_create_token_bucket(self, mock_redis):
        limiter = RateLimiter(mock_redis, strategy=RateLimitStrategy.TOKEN_BUCKET)
        bucket = limiter.create_limiter("test-key")
        assert isinstance(bucket, TokenBucket)

    def test_create_sliding_window(self, mock_redis):
        limiter = RateLimiter(mock_redis, strategy=RateLimitStrategy.SLIDING_WINDOW)
        window = limiter.create_limiter("test-key", max_calls=100, window_seconds=60.0)
        assert isinstance(window, SlidingWindowLog)


class TestRateLimitConfig:
    """速率限制配置测试"""

    def test_default_config(self):
        config = RateLimitConfig()
        assert config.max_tokens == 100
        assert config.refill_rate == 10.0
        assert config.initial_tokens is None

    def test_custom_config(self):
        config = RateLimitConfig(max_tokens=50, refill_rate=5.0, initial_tokens=25)
        assert config.max_tokens == 50
        assert config.refill_rate == 5.0
        assert config.initial_tokens == 25


class TestRateLimitResult:
    """速率限制结果测试"""

    def test_result_properties(self):
        result = RateLimitResult(
            allowed=True,
            remaining_tokens=99,
            retry_after_ms=None,
            limit_key="test-key",
        )
        assert result.allowed is True
        assert result.remaining_tokens == 99
        assert result.retry_after_ms is None
        assert result.limit_key == "test-key"

    def test_failure_result(self):
        result = RateLimitResult(
            allowed=False,
            remaining_tokens=0,
            retry_after_ms=100,
            limit_key="test-key",
        )
        assert result.allowed is False
        assert result.retry_after_ms == 100


class TestRateLimitStrategy:
    """速率限制策略测试"""

    def test_strategy_values(self):
        assert RateLimitStrategy.TOKEN_BUCKET.value == "token_bucket"
        assert RateLimitStrategy.FIXED_WINDOW.value == "fixed_window"
        assert RateLimitStrategy.SLIDING_WINDOW.value == "sliding_window"
