"""
Redis Stream 操作工具类

提供成本治理所需的 Redis Stream 原子操作：
1. 原子成本累加 (INCRBYFLOAT)
2. 成本记录写入 (XADD)
3. 分布式锁 (SET NX EX)
"""

import json
import logging
import time

import redis

logger = logging.getLogger(__name__)


class RedisStreamClient:
    """Redis Stream 客户端 - 用于分布式成本治理"""

    STREAM_KEY_PREFIX = "cost:stream:"
    COST_KEY_PREFIX = "cost:total:"
    LOCK_KEY_PREFIX = "cost:lock:"
    COUNTER_KEY_PREFIX = "cost:counter:"

    # Lua 脚本：原子成本累加 + 记录写入
    ATOMIC_COST_ACCUMULATE_LUA = """
    local stream_key = KEYS[1]
    local cost_key = KEYS[2]
    local record_data = ARGV[1]
    local cost_increment = tonumber(ARGV[2])

    -- 原子操作1: 成本累加
    local new_total = redis.call('INCRBYFLOAT', cost_key, cost_increment)

    -- 原子操作2: 记录写入 Stream
    local record_id = redis.call('XADD', stream_key, '*',
        'data', record_data,
        'cost', cost_increment,
        'timestamp', ARGV[3])

    return {tostring(new_total), record_id}
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        """
        初始化 Redis Stream 客户端

        Args:
            redis_url: Redis 连接 URL
        """
        self.redis = redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        self._script_sha: str | None = None

    def get_stream_key(self, date_suffix: str | None = None) -> str:
        """
        获取 Stream 键名

        Args:
            date_suffix: 日期后缀，格式 YYYYMMDD，默认当天

        Returns:
            Stream 键名
        """
        if date_suffix is None:
            date_suffix = time.strftime("%Y%m%d")
        return f"{self.STREAM_KEY_PREFIX}{date_suffix}"

    def get_cost_key(self, metric: str, date_suffix: str | None = None) -> str:
        """
        获取成本计数器键名

        Args:
            metric: 指标类型 (daily/weekly/monthly)
            date_suffix: 日期后缀

        Returns:
            成本计数器键名
        """
        if date_suffix is None:
            date_suffix = time.strftime("%Y%m%d")
        return f"{self.COST_KEY_PREFIX}{metric}:{date_suffix}"

    def atomic_record_and_accumulate(
        self,
        record_data: dict,
        cost_increment: float,
        date_suffix: str | None = None,
    ) -> tuple[float, str]:
        """
        原子操作：记录写入 + 成本累加

        Args:
            record_data: 记录数据 (dict)
            cost_increment: 成本增量
            date_suffix: 日期后缀

        Returns:
            (新成本总额, 记录ID)
        """
        stream_key = self.get_stream_key(date_suffix)
        cost_key = self.get_cost_key("daily", date_suffix)

        serialized_data = json.dumps(record_data, ensure_ascii=False)
        timestamp = str(time.time())

        # 使用 EVAL 直接执行 Lua 脚本，避免 SCRIPT LOAD 的 HELLO 问题
        result = self.redis.eval(
            self.ATOMIC_COST_ACCUMULATE_LUA,
            2,  # numkeys
            stream_key,
            cost_key,
            serialized_data,
            cost_increment,
            timestamp,
        )
        new_total = float(result[0])
        record_id = str(result[1])
        logger.debug(f"原子写入成功: record_id={record_id}, new_total={new_total}")
        return new_total, record_id

    def get_daily_cost(self, date_suffix: str | None = None) -> float:
        """
        获取日成本

        Args:
            date_suffix: 日期后缀

        Returns:
            日成本总额
        """
        cost_key = self.get_cost_key("daily", date_suffix)
        value = self.redis.get(cost_key)
        return float(value) if value else 0.0

    def get_records_count(self, date_suffix: str | None = None) -> int:
        """
        获取记录数量

        Args:
            date_suffix: 日期后缀

        Returns:
            记录数量
        """
        stream_key = self.get_stream_key(date_suffix)
        return self.redis.xlen(stream_key)

    def read_records(
        self,
        date_suffix: str | None = None,
        start_id: str = "-",
        end_id: str = "+",
        count: int = 100,
    ) -> list[tuple[str, dict]]:
        """
        读取记录

        Args:
            date_suffix: 日期后缀
            start_id: 起始 ID
            end_id: 结束 ID
            count: 最大数量

        Returns:
            [(record_id, data), ...]
        """
        stream_key = self.get_stream_key(date_suffix)
        records = self.redis.xrange(stream_key, start_id, end_id, count)
        return [(rid, json.loads(data["data"])) for rid, data in records]

    def acquire_lock(
        self,
        lock_key: str,
        ttl_seconds: int = 30,
        lock_value: str | None = None,
    ) -> bool:
        """
        获取分布式锁

        Args:
            lock_key: 锁键名
            ttl_seconds: 过期时间
            lock_value: 锁值

        Returns:
            是否获取成功
        """
        full_key = f"{self.LOCK_KEY_PREFIX}{lock_key}"
        if lock_value is None:
            import uuid

            lock_value = f"{uuid.uuid4()}:{time.time()}"

        acquired = self.redis.set(full_key, lock_value, nx=True, ex=ttl_seconds)
        return acquired is not None

    def release_lock(self, lock_key: str, lock_value: str) -> bool:
        """
        释放分布式锁 (Lua 保证原子性)

        Args:
            lock_key: 锁键名
            lock_value: 锁值

        Returns:
            是否释放成功
        """
        release_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        full_key = f"{self.LOCK_KEY_PREFIX}{lock_key}"
        result = self.redis.eval(release_script, 1, full_key, lock_value)
        return result == 1

    def health_check(self) -> bool:
        """健康检查"""
        try:
            self.redis.ping()
            return True
        except redis.ConnectionError:
            return False

    def close(self):
        """关闭连接"""
        self.redis.close()


# 全局客户端实例
_redis_stream_client: RedisStreamClient | None = None


def get_redis_stream_client() -> RedisStreamClient:
    """获取 Redis Stream 客户端单例"""
    global _redis_stream_client
    if _redis_stream_client is None:
        from src.config import settings

        _redis_stream_client = RedisStreamClient(settings.redis_url)
    return _redis_stream_client
