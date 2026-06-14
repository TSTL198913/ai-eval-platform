"""
限流器实现 - 基于令牌桶算法

支持多维度限流：用户级别、API级别、Worker级别。
使用 Redis 实现分布式环境下的原子操作。
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import redis

logger = logging.getLogger(__name__)


class RateLimitStrategy(Enum):
    """限流策略"""

    TOKEN_BUCKET = "token_bucket"  # 令牌桶
    FIXED_WINDOW = "fixed_window"  # 固定窗口
    SLIDING_WINDOW = "sliding_window"  # 滑动窗口


@dataclass
class RateLimitConfig:
    """限流配置"""

    max_tokens: int = 100  # 桶容量
    refill_rate: float = 10.0  # 每秒补充令牌数
    initial_tokens: Optional[int] = None  # 初始令牌数，None 表示满桶


@dataclass
class RateLimitResult:
    """限流结果"""

    allowed: bool
    remaining_tokens: int
    retry_after_ms: Optional[int]
    limit_key: str


class TokenBucket:
    """
    令牌桶算法实现

    特性:
    - 线程安全 (Redis 原子操作)
    - 支持分布式
    - 平滑限流
    """

    LUA_SCRIPT = """
    local key = KEYS[1]
    local capacity = tonumber(ARGV[1])
    local refill_rate = tonumber(ARGV[2])
    local now = tonumber(ARGV[3])
    local requested = tonumber(ARGV[4])

    -- 获取当前状态
    local data = redis.call('HMGET', key, 'tokens', 'last_update')
    local tokens = tonumber(data[1]) or capacity
    local last_update = tonumber(data[2]) or now

    -- 计算应该补充的令牌数
    local elapsed = now - last_update
    local add_tokens = elapsed * refill_rate
    tokens = math.min(capacity, tokens + add_tokens)

    -- 检查是否可以获取令牌
    local allowed = 0
    local remaining = tokens

    if tokens >= requested then
        tokens = tokens - requested
        remaining = tokens
        allowed = 1
    end

    -- 更新状态
    redis.call('HMSET', key, 'tokens', tokens, 'last_update', now)
    redis.call('EXPIRE', key, 3600)  -- 1小时过期

    return {allowed, remaining}
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        key: str,
        config: Optional[RateLimitConfig] = None,
    ):
        self.redis = redis_client
        self.key = f"ratelimit:token_bucket:{key}"
        self.config = config or RateLimitConfig()
        self._script = self.redis.register_script(self.LUA_SCRIPT)

    def allow(self, tokens: int = 1) -> RateLimitResult:
        """
        检查是否允许消耗令牌

        Args:
            tokens: 要消耗的令牌数

        Returns:
            RateLimitResult: 限流结果
        """
        now = time.time()

        result = self._script(
            keys=[self.key],
            args=[
                self.config.max_tokens,
                self.config.refill_rate,
                now,
                tokens,
            ],
        )

        allowed = bool(result[0])
        remaining = int(result[1])

        if not allowed:
            # 计算需要等待多久才能获取一个令牌
            retry_after_ms = int(1000 / self.config.refill_rate)
        else:
            retry_after_ms = None

        return RateLimitResult(
            allowed=allowed,
            remaining_tokens=remaining,
            retry_after_ms=retry_after_ms,
            limit_key=self.key,
        )


class SlidingWindowLog:
    """
    滑动窗口日志算法实现

    更精确的限流，但内存占用较高
    """

    LUA_SCRIPT = """
    local key = KEYS[1]
    local window_ms = tonumber(ARGV[1])
    local max_calls = tonumber(ARGV[2])
    local now = tonumber(ARGV[3])
    local window_start = now - window_ms

    -- 删除窗口外的记录
    redis.call('ZREMRANGEBYSCORE', key, 0, window_start)

    -- 统计当前窗口内的请求数
    local current_count = redis.call('ZCARD', key)

    local allowed = 0
    local remaining = max_calls - current_count

    if current_count < max_calls then
        -- 添加新请求
        redis.call('ZADD', key, now, now .. ':' .. math.random())
        redis.call('EXPIRE', key, math.ceil(window_ms / 1000) + 1)
        allowed = 1
        remaining = max_calls - current_count - 1
    end

    return {allowed, remaining}
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        key: str,
        max_calls: int,
        window_seconds: float,
    ):
        self.redis = redis_client
        self.key = f"ratelimit:sliding:{key}"
        self.max_calls = max_calls
        self.window_ms = int(window_seconds * 1000)
        self._script = self.redis.register_script(self.LUA_SCRIPT)

    def allow(self) -> RateLimitResult:
        """检查是否允许请求"""
        now_ms = int(time.time() * 1000)

        result = self._script(
            keys=[self.key],
            args=[self.window_ms, self.max_calls, now_ms],
        )

        allowed = bool(result[0])
        remaining = int(result[1])

        if not allowed:
            retry_after_ms = self.window_ms // self.max_calls
        else:
            retry_after_ms = None

        return RateLimitResult(
            allowed=allowed,
            remaining_tokens=remaining,
            retry_after_ms=retry_after_ms,
            limit_key=self.key,
        )


class RateLimiter:
    """
    分布式限流器

    支持多种限流策略，适用于不同场景:
    - TOKEN_BUCKET: API 限流，平滑控制
    - SLIDING_WINDOW: 精确限流，允许突发
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        strategy: RateLimitStrategy = RateLimitStrategy.TOKEN_BUCKET,
    ):
        self.redis = redis_client
        self.strategy = strategy

    def create_limiter(
        self,
        key: str,
        config: Optional[RateLimitConfig] = None,
        max_calls: Optional[int] = None,
        window_seconds: Optional[float] = None,
    ) -> TokenBucket | SlidingWindowLog:
        """创建限流器"""
        if self.strategy == RateLimitStrategy.TOKEN_BUCKET:
            return TokenBucket(self.redis, key, config)
        elif self.strategy == RateLimitStrategy.SLIDING_WINDOW:
            return SlidingWindowLog(
                self.redis,
                key,
                max_calls=max_calls or 100,
                window_seconds=window_seconds or 60.0,
            )
        else:
            return TokenBucket(self.redis, key, config)


class MultiDimensionRateLimiter:
    """
    多维度限流器

    支持用户、API、IP等多维度限流
    """

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self._limiters: dict[str, TokenBucket] = {}

    def _get_limiter(self, dimension: str, config: RateLimitConfig) -> TokenBucket:
        """获取或创建维度限流器"""
        if dimension not in self._limiters:
            self._limiters[dimension] = TokenBucket(self.redis, dimension, config)
        return self._limiters[dimension]

    def check(
        self,
        user_id: Optional[str] = None,
        api_key: Optional[str] = None,
        ip: Optional[str] = None,
        tokens: int = 1,
    ) -> list[RateLimitResult]:
        """
        检查多个维度的限流

        任意一个维度超限都会拒绝
        """
        results = []

        if user_id:
            limiter = self._get_limiter(
                f"user:{user_id}",
                RateLimitConfig(max_tokens=1000, refill_rate=100),
            )
            results.append(limiter.allow(tokens))

        if api_key:
            limiter = self._get_limiter(
                f"apikey:{api_key}",
                RateLimitConfig(max_tokens=100, refill_rate=10),
            )
            results.append(limiter.allow(tokens))

        if ip:
            limiter = self._get_limiter(
                f"ip:{ip}",
                RateLimitConfig(max_tokens=50, refill_rate=5),
            )
            results.append(limiter.allow(tokens))

        return results

    def is_allowed(
        self,
        user_id: Optional[str] = None,
        api_key: Optional[str] = None,
        ip: Optional[str] = None,
    ) -> tuple[bool, Optional[RateLimitResult]]:
        """
        检查是否允许请求

        Returns:
            (is_allowed, first_failed_result)
        """
        results = self.check(user_id, api_key, ip)
        for result in results:
            if not result.allowed:
                return False, result
        return True, None


async def rate_limit_async(
    limiter: TokenBucket,
    tokens: int = 1,
    max_retries: int = 10,
    retry_delay: float = 0.1,
) -> RateLimitResult:
    """
    异步限流检查

    如果被限流，等待后重试
    """
    for _ in range(max_retries):
        result = limiter.allow(tokens)
        if result.allowed:
            return result
        await asyncio.sleep(
            result.retry_after_ms / 1000 if result.retry_after_ms else retry_delay
        )

    return RateLimitResult(
        allowed=False,
        remaining_tokens=0,
        retry_after_ms=None,
        limit_key=limiter.key,
    )
