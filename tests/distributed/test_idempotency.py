"""分布式幂等性测试"""

import pytest
from unittest.mock import MagicMock

from src.distributed.idempotency import IdempotencyChecker, IdempotencyConfig, IdempotencyError


class TestIdempotencyCheckerBasic:
    """幂等性检查基础测试"""

    @pytest.fixture
    def mock_redis(self):
        mock = MagicMock()
        mock.exists = MagicMock(return_value=0)
        mock.setex = MagicMock()
        mock.setnx = MagicMock(return_value=True)
        mock.set = MagicMock()
        mock.get = MagicMock(return_value=None)
        return mock

    @pytest.fixture
    def checker(self, mock_redis):
        return IdempotencyChecker(mock_redis)

    def test_check_new_request(self, checker, mock_redis):
        result = checker.check("unique-id-123")
        assert result is True

    def test_check_existing_request(self, checker, mock_redis):
        mock_redis.exists = MagicMock(return_value=1)
        result = checker.check("existing-id")
        assert result is False

    def test_mark_processing(self, checker, mock_redis):
        result = checker.mark_processing("processing-id")
        mock_redis.setnx.assert_called_once()

    def test_mark_processed(self, checker, mock_redis):
        checker.mark_processed("processed-id", "result")
        mock_redis.set.assert_called_once()

    def test_get_cached_result(self, checker, mock_redis):
        import json
        mock_redis.get = MagicMock(return_value=json.dumps({
            "status": "processed",
            "result": "cached-result",
            "timestamp": 1234567890.0,
            "metadata": {}
        }).encode())
        result = checker.get_cached_result("cached-id")
        assert result == "cached-result"

    def test_get_nonexistent_result(self, checker, mock_redis):
        mock_redis.get = MagicMock(return_value=None)
        result = checker.get_cached_result("nonexistent-id")
        assert result is None


class TestIdempotencyCheckerConfig:
    """幂等性检查配置测试"""

    @pytest.fixture
    def mock_redis(self):
        mock = MagicMock()
        mock.exists = MagicMock(return_value=0)
        return mock

    def test_default_config(self, mock_redis):
        checker = IdempotencyChecker(mock_redis)
        assert checker._config.ttl_seconds == 3600

    def test_custom_config(self, mock_redis):
        config = IdempotencyConfig(ttl_seconds=1800)
        checker = IdempotencyChecker(mock_redis, config=config)
        assert checker._config.ttl_seconds == 1800


class TestIdempotencyCheckerEdgeCases:
    """幂等性检查边界情况测试"""

    @pytest.fixture
    def mock_redis(self):
        mock = MagicMock()
        mock.exists = MagicMock(return_value=0)
        return mock

    def test_empty_id(self, mock_redis):
        checker = IdempotencyChecker(mock_redis)
        result = checker.check("")
        assert isinstance(result, bool)

    def test_none_id(self, mock_redis):
        checker = IdempotencyChecker(mock_redis)
        result = checker.check(None)
        assert isinstance(result, bool)


class TestIdempotencyError:
    """幂等性错误测试"""

    def test_error_message(self):
        error = IdempotencyError("test message")
        assert "[DUPLICATE_REQUEST]" in str(error)
        assert "test message" in str(error)

    def test_error_inherits_exception(self):
        error = IdempotencyError("test")
        assert isinstance(error, Exception)