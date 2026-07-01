"""分布式锁测试"""

from unittest.mock import MagicMock

import pytest

from src.distributed.lock import DistributedLock, LockResult, LockState


class TestDistributedLockBasic:
    """分布式锁基础测试"""

    @pytest.fixture
    def mock_redis(self):
        mock = MagicMock()
        mock.set = MagicMock(return_value=True)
        return mock

    def test_acquire_success(self, mock_redis):
        lock = DistributedLock(mock_redis, "test-lock")
        result = lock.acquire()
        assert result.state == LockState.ACQUIRED
        assert lock.is_acquired is True

    def test_acquire_failure(self, mock_redis):
        mock_redis.set = MagicMock(return_value=False)
        lock = DistributedLock(mock_redis, "test-lock", retry_times=1)
        result = lock.acquire()
        assert result.state == LockState.NOT_ACQUIRED
        assert lock.is_acquired is False

    def test_release_success(self, mock_redis):
        mock_redis.set = MagicMock(return_value=True)
        mock_redis.eval = MagicMock(return_value=1)

        lock = DistributedLock(mock_redis, "test-lock")
        lock.acquire()
        result = lock.release()
        assert result is True
        assert lock.is_acquired is False

    def test_release_not_acquired(self, mock_redis):
        lock = DistributedLock(mock_redis, "test-lock")
        result = lock.release()
        assert result is False

    def test_context_manager_success(self, mock_redis):
        mock_redis.set = MagicMock(return_value=True)
        mock_redis.eval = MagicMock(return_value=1)

        lock = DistributedLock(mock_redis, "test-lock")

        with lock:
            assert lock.is_acquired is True

        assert lock.is_acquired is False

    def test_context_manager_failure(self, mock_redis):
        mock_redis.set = MagicMock(return_value=False)

        lock = DistributedLock(mock_redis, "test-lock", retry_times=1)

        with pytest.raises(RuntimeError):
            with lock:
                pass


class TestDistributedLockRetry:
    """分布式锁重试测试"""

    @pytest.fixture
    def mock_redis(self):
        mock = MagicMock()
        mock.set = MagicMock(side_effect=[False, True])
        return mock

    def test_retry_success(self, mock_redis):
        lock = DistributedLock(mock_redis, "retry-lock", retry_times=2)
        result = lock.acquire()
        assert result.state == LockState.ACQUIRED
        assert mock_redis.set.call_count == 2

    def test_retry_exhausted(self, mock_redis):
        mock_redis.set = MagicMock(return_value=False)
        lock = DistributedLock(mock_redis, "exhaust-lock", retry_times=3)
        result = lock.acquire()
        assert result.state == LockState.NOT_ACQUIRED
        assert mock_redis.set.call_count == 3


class TestDistributedLockExtend:
    """分布式锁延长测试"""

    @pytest.fixture
    def mock_redis(self):
        mock = MagicMock()
        mock.set = MagicMock(return_value=True)
        mock.eval = MagicMock(return_value=1)
        return mock

    def test_extend_success(self, mock_redis):
        lock = DistributedLock(mock_redis, "extend-lock")
        lock.acquire()
        result = lock.extend(30.0)
        assert result is True

    def test_extend_not_acquired(self, mock_redis):
        lock = DistributedLock(mock_redis, "extend-lock")
        result = lock.extend(30.0)
        assert result is False


class TestLockResult:
    """锁结果测�?""

    def test_lock_result_properties(self):
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


class TestLockState:
    """锁状态测�?""

    def test_lock_state_values(self):
        assert LockState.ACQUIRED.value == "acquired"
        assert LockState.NOT_ACQUIRED.value == "not_acquired"
        assert LockState.RELEASED.value == "released"
