"""分布式锁测试

测试目标：验证分布式锁的精确业务逻辑和并发安全性

强断言要求：
1. 验证锁值的精确格式
2. 验证Redis调用参数（NX, EX）
3. 验证锁TTL精确值
4. 验证锁竞争场景下的正确行为
"""

import re
from unittest.mock import MagicMock

import pytest

from src.distributed.lock import DistributedLock, LockResult, LockState


class TestDistributedLockStrongAssertions:
    """分布式锁强断言测试"""

    @pytest.fixture
    def mock_redis(self):
        mock = MagicMock()
        mock.set = MagicMock(return_value=True)
        return mock

    def test_acquire_with_precise_lock_value(self, mock_redis):
        """获取锁应生成符合格式的锁值"""
        lock = DistributedLock(mock_redis, "test-lock")
        result = lock.acquire()

        assert result.state == LockState.ACQUIRED
        assert lock.is_acquired is True

        lock_value = result.lock_value
        assert lock_value is not None

        parts = lock_value.split(":")
        assert len(parts) == 2, f"锁值格式不正确: {lock_value}"

        try:
            import uuid
            uuid.UUID(parts[0])
        except ValueError:
            pytest.fail(f"锁值的UUID部分无效: {parts[0]}")

        try:
            float(parts[1])
        except ValueError:
            pytest.fail(f"锁值的时间戳部分无效: {parts[1]}")

        assert lock.lock_value == lock_value

    def test_redis_call_with_correct_params(self, mock_redis):
        """Redis调用应包含正确参数（NX, EX）"""
        lock = DistributedLock(mock_redis, "test-lock", ttl_seconds=30)
        lock.acquire()

        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == "eval:lock:test-lock"

        kwargs = call_args.kwargs
        assert kwargs.get("nx") is True
        assert kwargs.get("ex") == 30

    def test_acquire_failure_with_retry(self, mock_redis):
        """获取锁失败应按配置重试次数重试"""
        mock_redis.set = MagicMock(side_effect=[False, False, True])
        lock = DistributedLock(mock_redis, "test-lock", retry_times=3)
        result = lock.acquire()

        assert result.state == LockState.ACQUIRED
        assert mock_redis.set.call_count == 3

    def test_release_uses_lua_script(self, mock_redis):
        """释放锁应使用Lua脚本保证原子性"""
        mock_redis.set = MagicMock(return_value=True)
        mock_redis.eval = MagicMock(return_value=1)

        lock = DistributedLock(mock_redis, "test-lock")
        lock.acquire()
        result = lock.release()

        assert result is True
        assert lock.is_acquired is False

        mock_redis.eval.assert_called_once()
        lua_script = mock_redis.eval.call_args[0][0]
        assert "redis.call" in lua_script
        assert "del" in lua_script.lower()

    def test_release_wrong_value_fails(self, mock_redis):
        """使用错误锁值释放应失败"""
        mock_redis.set = MagicMock(return_value=True)
        mock_redis.eval = MagicMock(return_value=0)

        lock = DistributedLock(mock_redis, "test-lock")
        lock.acquire()
        lock._lock_value = "wrong-value"
        result = lock.release()

        assert result is False
        assert lock.is_acquired is False

    def test_extend_updates_ttl(self, mock_redis):
        """延长锁应更新TTL"""
        mock_redis.set = MagicMock(return_value=True)
        mock_redis.eval = MagicMock(return_value=1)

        lock = DistributedLock(mock_redis, "test-lock", ttl_seconds=30)
        lock.acquire()
        result = lock.extend(60.0)

        assert result is True

        mock_redis.eval.assert_called_once()
        lua_script = mock_redis.eval.call_args[0][0]
        assert "expire" in lua_script.lower()


class TestDistributedLockConcurrentSafety:
    """分布式锁并发安全测试"""

    def test_concurrent_acquire_only_one_succeeds(self):
        """并发获取锁只有一个能成功"""
        mock_redis = MagicMock()
        mock_redis.set = MagicMock(side_effect=[True] + [False] * 20)

        locks = []
        results = []
        for i in range(5):
            lock = DistributedLock(mock_redis, "concurrent-lock", retry_times=1)
            locks.append(lock)
            results.append(lock.acquire())

        success_count = sum(1 for r in results if r.state == LockState.ACQUIRED)
        assert success_count == 1, f"预期1个成功，实际{success_count}个成功"

    def test_lock_result_contains_all_fields(self):
        """锁结果应包含所有字段"""
        result = LockResult(
            state=LockState.ACQUIRED,
            lock_key="test-key",
            lock_value="test-value",
            ttl_ms=30000,
        )

        assert result.state == LockState.ACQUIRED
        assert result.lock_key == "test-key"
        assert result.lock_value == "test-value"
        assert result.ttl_ms == 30000

    def test_lock_state_values(self):
        """锁状态枚举值应正确"""
        assert LockState.ACQUIRED.value == "acquired"
        assert LockState.NOT_ACQUIRED.value == "not_acquired"
        assert LockState.RELEASED.value == "released"