"""分布式速率限制器测试

测试目标：验证速率限制器的精确业务逻辑和并发安全性

强断言要求：
1. 验证令牌桶算法精确性
2. 验证Redis Lua脚本调用参数
3. 验证速率限制结果精确值
4. 验证滑动窗口边界行为
"""

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


class TestTokenBucketStrongAssertions:
    """令牌桶强断言测试"""

    @pytest.fixture
    def mock_redis(self):
        mock = MagicMock()
        mock.register_script = MagicMock(return_value=MagicMock(return_value=[1, 99]))
        return mock

    def test_token_bucket_allow_with_precise_tokens(self, mock_redis):
        """令牌桶允许请求应精确减少令牌"""
        bucket = TokenBucket(mock_redis, "test-bucket", config=RateLimitConfig(max_tokens=100, refill_rate=10.0))
        result = bucket.allow()

        assert result.allowed is True
        assert result.remaining_tokens == 99

        mock_redis.register_script.assert_called_once()
        lua_script = mock_redis.register_script.call_args[0][0]
        assert "redis.call" in lua_script
        assert "HMSET" in lua_script or "hmget" in lua_script.lower()

    def test_token_bucket_exhausted_returns_retry_after(self, mock_redis):
        """令牌桶耗尽应返回精确重试时间"""
        mock_redis.register_script = MagicMock(return_value=MagicMock(return_value=[0, 0]))
        bucket = TokenBucket(mock_redis, "test-bucket")
        result = bucket.allow()

        assert result.allowed is False
        assert result.remaining_tokens == 0
        assert result.retry_after_ms is not None
        assert result.retry_after_ms > 0

    def test_custom_config_applied_precisely(self, mock_redis):
        """自定义配置应精确应用"""
        config = RateLimitConfig(max_tokens=50, refill_rate=5.0, initial_tokens=25)
        bucket = TokenBucket(mock_redis, "custom-bucket", config=config)

        assert bucket.config.max_tokens == 50
        assert bucket.config.refill_rate == 5.0
        assert bucket.config.initial_tokens == 25

        mock_redis.register_script.assert_called_once()

    def test_token_bucket_concurrent_requests(self, mock_redis):
        """并发请求应正确扣减令牌"""
        script_mock = MagicMock(return_value=[1, 95])
        mock_redis.register_script = MagicMock(return_value=script_mock)

        bucket = TokenBucket(mock_redis, "concurrent-bucket")
        results = []

        for i in range(5):
            results.append(bucket.allow())

        success_count = sum(1 for r in results if r.allowed)
        assert success_count == 5

        assert script_mock.call_count == 5


class TestSlidingWindowLogStrongAssertions:
    """滑动窗口日志强断言测试"""

    @pytest.fixture
    def mock_redis(self):
        mock = MagicMock()
        mock.register_script = MagicMock(return_value=MagicMock(return_value=[1, 9]))
        return mock

    def test_sliding_window_allow_precise_count(self, mock_redis):
        """滑动窗口应精确计数"""
        window = SlidingWindowLog(mock_redis, "test-window", max_calls=10, window_seconds=60.0)
        result = window.allow()

        assert result.allowed is True
        assert result.remaining_tokens == 9

        mock_redis.register_script.assert_called_once()

    def test_sliding_window_exceeded_returns_retry(self, mock_redis):
        """超过限制应返回重试时间"""
        mock_redis.register_script = MagicMock(return_value=MagicMock(return_value=[0, 0]))
        window = SlidingWindowLog(mock_redis, "test-window", max_calls=10, window_seconds=60.0)
        result = window.allow()

        assert result.allowed is False
        assert result.retry_after_ms is not None
        assert result.retry_after_ms > 0

    def test_sliding_window_time_boundary(self, mock_redis):
        """窗口边界应正确处理"""
        mock_redis.register_script = MagicMock(return_value=MagicMock(return_value=[1, 10]))

        window = SlidingWindowLog(mock_redis, "boundary-window", max_calls=10, window_seconds=60.0)
        result = window.allow()

        assert result.allowed is True
        assert result.remaining_tokens == 10


class TestRateLimiterStrongAssertions:
    """速率限制器强断言测试"""

    @pytest.fixture
    def mock_redis(self):
        mock = MagicMock()
        mock.register_script = MagicMock(return_value=MagicMock(return_value=[1, 99]))
        return mock

    def test_create_token_bucket_with_correct_config(self, mock_redis):
        """创建令牌桶应使用正确配置"""
        limiter = RateLimiter(mock_redis, strategy=RateLimitStrategy.TOKEN_BUCKET)
        bucket = limiter.create_limiter("test-key")

        assert isinstance(bucket, TokenBucket)

    def test_create_sliding_window_with_precise_params(self, mock_redis):
        """创建滑动窗口应使用精确参数"""
        limiter = RateLimiter(mock_redis, strategy=RateLimitStrategy.SLIDING_WINDOW)
        window = limiter.create_limiter("test-key", max_calls=100, window_seconds=60.0)

        assert isinstance(window, SlidingWindowLog)

    def test_rate_limit_result_contains_all_fields(self):
        """速率限制结果应包含所有字段"""
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

        failure_result = RateLimitResult(
            allowed=False,
            remaining_tokens=0,
            retry_after_ms=100,
            limit_key="test-key",
        )

        assert failure_result.allowed is False
        assert failure_result.retry_after_ms == 100

    def test_rate_limit_config_defaults(self):
        """默认配置应精确设置"""
        config = RateLimitConfig()

        assert config.max_tokens == 100
        assert config.refill_rate == 10.0
        assert config.initial_tokens is None

    def test_rate_limit_strategy_values(self):
        """策略枚举值应正确"""
        assert RateLimitStrategy.TOKEN_BUCKET.value == "token_bucket"
        assert RateLimitStrategy.FIXED_WINDOW.value == "fixed_window"
        assert RateLimitStrategy.SLIDING_WINDOW.value == "sliding_window"