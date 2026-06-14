"""
分布式锁实现 - 基于 Redis Redlock 算法

提供分布式环境下的互斥访问能力，防止任务重复执行。
"""

import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum

import redis


class LockState(Enum):
    """锁状态"""

    ACQUIRED = "acquired"
    NOT_ACQUIRED = "not_acquired"
    RELEASED = "released"


@dataclass
class LockResult:
    """锁获取结果"""

    state: LockState
    lock_key: str
    lock_value: str
    ttl_ms: int


class DistributedLock:
    """
    分布式锁实现

    特性:
    - 单实例 Redis 锁
    - 自动过期 (TTL)
    - 可重入
    - 上下文管理器支持
    """

    LOCK_PREFIX = "eval:lock:"

    def __init__(
        self,
        redis_client: redis.Redis,
        key: str,
        ttl_seconds: float = 30.0,
        retry_times: int = 3,
        retry_delay: float = 0.1,
    ):
        self.redis = redis_client
        self.key = f"{self.LOCK_PREFIX}{key}"
        self.ttl_seconds = ttl_seconds
        self.retry_times = retry_times
        self.retry_delay = retry_delay
        self.lock_value: str | None = None
        self._acquired = False

    def acquire(self) -> LockResult:
        """
        尝试获取锁

        使用 SET NX EX 原子操作确保锁的互斥性
        """
        self.lock_value = f"{uuid.uuid4()}:{time.time()}"

        for _ in range(self.retry_times):
            # SET key value NX EX seconds - 原子操作
            acquired = self.redis.set(
                self.key,
                self.lock_value,
                nx=True,  # Only set if Not eXists
                ex=int(self.ttl_seconds),  # Expiration in seconds
            )

            if acquired:
                self._acquired = True
                return LockResult(
                    state=LockState.ACQUIRED,
                    lock_key=self.key,
                    lock_value=self.lock_value,
                    ttl_ms=int(self.ttl_seconds * 1000),
                )

            time.sleep(self.retry_delay)

        return LockResult(
            state=LockState.NOT_ACQUIRED,
            lock_key=self.key,
            lock_value="",
            ttl_ms=0,
        )

    def release(self) -> bool:
        """
        释放锁

        使用 Lua 脚本确保只删除自己持有的锁
        """
        if not self._acquired or not self.lock_value:
            return False

        # Lua 脚本：原子性地检查并删除
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """

        try:
            result = self.redis.eval(lua_script, 1, self.key, self.lock_value)
            self._acquired = False
            return result == 1
        except Exception:
            return False

    def extend(self, additional_seconds: float) -> bool:
        """
        延长锁的 TTL

        用于长任务执行时的锁续期
        """
        if not self._acquired or not self.lock_value:
            return False

        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("expire", KEYS[1], ARGV[2])
        else
            return 0
        end
        """

        result = self.redis.eval(lua_script, 1, self.key, self.lock_value, int(additional_seconds))
        return result == 1

    @property
    def is_acquired(self) -> bool:
        return self._acquired

    def __enter__(self) -> "DistributedLock":
        result = self.acquire()
        if result.state != LockState.ACQUIRED:
            raise RuntimeError(f"Failed to acquire lock: {self.key}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False


class RedLock:
    """
    Redlock 多节点分布式锁

    在多个独立的 Redis 实例上获取锁，提高锁的可靠性。
    多数节点成功即认为获取锁成功。

    注意: 这里实现简化版，单实例场景足够使用。
    生产环境建议使用 redisson 或 redis-py-cluster。
    """

    def __init__(self, redis_clients: list[redis.Redis], ttl_seconds: float = 10.0):
        self.redis_clients = redis_clients
        self.ttl_seconds = ttl_seconds
        self.quorum = len(redis_clients) // 2 + 1

    def lock(self, resource: str) -> str | None:
        """
        获取多节点锁

        Returns:
            lock_value if successful, None otherwise
        """
        lock_value = f"{uuid.uuid4()}:{time.time()}"
        acquired_count = 0

        for redis_client in self.redis_clients:
            try:
                if redis_client.set(
                    f"eval:lock:{resource}",
                    lock_value,
                    nx=True,
                    ex=int(self.ttl_seconds),
                ):
                    acquired_count += 1
            except Exception:
                pass

        if acquired_count >= self.quorum:
            return lock_value
        return None

    def unlock(self, resource: str, lock_value: str) -> bool:
        """
        释放多节点锁
        """
        released_count = 0

        for redis_client in self.redis_clients:
            try:
                lua_script = """
                if redis.call("get", KEYS[1]) == ARGV[1] then
                    return redis.call("del", KEYS[1])
                else
                    return 0
                end
                """
                if redis_client.eval(lua_script, 1, f"eval:lock:{resource}", lock_value):
                    released_count += 1
            except Exception:
                pass

        return released_count >= self.quorum


@contextmanager
def distributed_lock(
    redis_client: redis.Redis,
    key: str,
    ttl_seconds: float = 30.0,
):
    """
    分布式锁上下文管理器便捷函数
    """
    lock = DistributedLock(redis_client, key, ttl_seconds)
    try:
        result = lock.acquire()
        if result.state != LockState.ACQUIRED:
            raise RuntimeError(f"Failed to acquire distributed lock: {key}")
        yield lock
    finally:
        lock.release()
