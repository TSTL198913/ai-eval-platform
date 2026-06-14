"""补充测试 distributed/rate_limiter.py - 限流器"""

from unittest.mock import Mock

import pytest

from src.distributed.rate_limiter import (
    RateLimitConfig,
    RateLimitResult,
    RateLimitStrategy,
    SlidingWindowLog,
    TokenBucket,
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

    def test_allow_denied(self, window, mock_redis):
        mock_script = Mock()
        mock_script.return_value = [0, 0]
        window._script = mock_script

        result = window.allow()
        assert result.allowed is False
        assert result.retry_after_ms is not None


class TestRateLimitStrategy:
    """测试限流策略枚举"""

    def test_values(self):
        assert RateLimitStrategy.TOKEN_BUCKET.value == "token_bucket"
        assert RateLimitStrategy.FIXED_WINDOW.value == "fixed_window"
        assert RateLimitStrategy.SLIDING_WINDOW.value == "sliding_window"
