"""测试 distributed/lock.py - 分布式锁核心模块"""

import time
import uuid
from unittest.mock import Mock, patch

import pytest
import redis

from src.distributed.lock import (
    DistributedLock,
    LockResult,
    LockState,
    RedLock,
)


class TestLockResult:
    """测试锁结果实体"""

    def test_acquired_result(self):
        result = LockResult(
            state=LockState.ACQUIRED,
            lock_key="test:key",
            lock_value="uuid:123",
            ttl_ms=30000,
        )
        assert result.state == LockState.ACQUIRED
        assert result.ttl_ms == 30000

    def test_not_acquired_result(self):
        result = LockResult(
            state=LockState.NOT_ACQUIRED,
            lock_key="test:key",
            lock_value="",
            ttl_ms=0,
        )
        assert result.state == LockState.NOT_ACQUIRED


class TestDistributedLock:
    """测试分布式锁"""

    @pytest.fixture
    def mock_redis(self):
        mock = Mock(spec=redis.Redis)
        mock.set.return_value = True
        mock.eval.return_value = 1
        return mock

    @pytest.fixture
    def lock(self, mock_redis):
        return DistributedLock(
            redis_client=mock_redis,
            key="test_resource",
            ttl_seconds=30.0,
            retry_times=3,
            retry_delay=0.01,
        )

    def test_initial_state(self, lock):
        assert lock.is_acquired is False
        assert lock.lock_value is None
        assert lock.key == "eval:lock:test_resource"

    def test_acquire_success(self, lock, mock_redis):
        mock_redis.set.return_value = True
        result = lock.acquire()
        assert result.state == LockState.ACQUIRED
        assert lock.is_acquired is True
        assert lock.lock_value is not None
        mock_redis.set.assert_called_with(
            lock.key,
            lock.lock_value,
            nx=True,
            ex=30,
        )

    def test_acquire_failure(self, lock, mock_redis):
        mock_redis.set.return_value = None
        result = lock.acquire()
        assert result.state == LockState.NOT_ACQUIRED
        assert lock.is_acquired is False

    def test_acquire_with_retry(self, lock, mock_redis):
        mock_redis.set.side_effect = [None, None, True]
        result = lock.acquire()
        assert result.state == LockState.ACQUIRED
        assert mock_redis.set.call_count == 3

    def test_acquire_all_retries_fail(self, lock, mock_redis):
        mock_redis.set.return_value = None
        result = lock.acquire()
        assert result.state == LockState.NOT_ACQUIRED
        assert mock_redis.set.call_count == 3

    def test_release_success(self, lock, mock_redis):
        lock.acquire()
        mock_redis.eval.return_value = 1
        result = lock.release()
        assert result is True
        assert lock.is_acquired is False

    def test_release_not_acquired(self, lock):
        result = lock.release()
        assert result is False

    def test_release_wrong_value(self, lock, mock_redis):
        lock.acquire()
        mock_redis.eval.return_value = 0
        result = lock.release()
        assert result is False

    def test_extend_success(self, lock, mock_redis):
        lock.acquire()
        mock_redis.eval.return_value = 1
        result = lock.extend(60)
        assert result is True

    def test_extend_not_acquired(self, lock):
        result = lock.extend(60)
        assert result is False

    def test_context_manager_success(self, mock_redis):
        mock_redis.set.return_value = True
        mock_redis.eval.return_value = 1
        lock = DistributedLock(mock_redis, "ctx_test")
        with lock as l:
            assert l.is_acquired is True
        assert lock.is_acquired is False

    def test_context_manager_failure(self, mock_redis):
        mock_redis.set.return_value = None
        lock = DistributedLock(mock_redis, "ctx_fail", retry_times=1, retry_delay=0.01)
        with pytest.raises(RuntimeError, match="Failed to acquire lock"):
            with lock:
                pass

    def test_release_exception_handled(self, lock, mock_redis):
        lock.acquire()
        mock_redis.eval.side_effect = Exception("Redis error")
        result = lock.release()
        assert result is False

    def test_lock_value_format(self, lock, mock_redis):
        mock_redis.set.return_value = True
        lock.acquire()
        assert ":" in lock.lock_value
        parts = lock.lock_value.split(":")
        assert len(parts) == 2
        # 验证 UUID 格式
        uuid.UUID(parts[0])


class TestRedLock:
    """测试 Redlock 多节点锁"""

    def test_single_node_success(self):
        mock_redis = Mock(spec=redis.Redis)
        mock_redis.set.return_value = True
        redlock = RedLock([mock_redis], ttl_seconds=10.0)
        result = redlock.lock("resource")
        assert result is not None
        mock_redis.set.assert_called_once()

    def test_single_node_failure(self):
        mock_redis = Mock(spec=redis.Redis)
        mock_redis.set.return_value = None
        redlock = RedLock([mock_redis], ttl_seconds=10.0)
        result = redlock.lock("resource")
        assert result is None

    def test_multi_node_quorum(self):
        redis1 = Mock(spec=redis.Redis)
        redis2 = Mock(spec=redis.Redis)
        redis3 = Mock(spec=redis.Redis)

        redis1.set.return_value = True
        redis2.set.return_value = True
        redis3.set.return_value = None

        redlock = RedLock([redis1, redis2, redis3], ttl_seconds=10.0)
        result = redlock.lock("resource")
        assert result is not None

    def test_multi_node_no_quorum(self):
        redis1 = Mock(spec=redis.Redis)
        redis2 = Mock(spec=redis.Redis)
        redis3 = Mock(spec=redis.Redis)

        redis1.set.return_value = True
        redis2.set.return_value = None
        redis3.set.return_value = None

        redlock = RedLock([redis1, redis2, redis3], ttl_seconds=10.0)
        result = redlock.lock("resource")
        assert result is None

    def test_redis_exception_handled(self):
        mock_redis = Mock(spec=redis.Redis)
        mock_redis.set.side_effect = Exception("Connection error")
        redlock = RedLock([mock_redis], ttl_seconds=10.0)
        result = redlock.lock("resource")
        assert result is None

    def test_lock_value_format(self):
        mock_redis = Mock(spec=redis.Redis)
        mock_redis.set.return_value = True
        redlock = RedLock([mock_redis], ttl_seconds=10.0)
        result = redlock.lock("resource")
        assert ":" in result
