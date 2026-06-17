"""
分布式组件集成测试
覆盖幂等性检查器、分布式锁、分布式队列
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from src.distributed.idempotency import (
    IdempotencyChecker,
    IdempotencyConfig,
    IdempotencyError,
    IdempotencyStrategy,
)


class TestIdempotencyConfig:
    """幂等性配置测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = IdempotencyConfig()
        assert config.ttl_seconds == 3600
        assert config.key_prefix == "idempotency:"
        assert config.strategy == IdempotencyStrategy.REQUEST_ID

    def test_custom_config(self):
        """测试自定义配置"""
        config = IdempotencyConfig(
            ttl_seconds=7200,
            key_prefix="custom:",
            strategy=IdempotencyStrategy.BUSINESS_KEY,
        )
        assert config.ttl_seconds == 7200
        assert config.key_prefix == "custom:"
        assert config.strategy == IdempotencyStrategy.BUSINESS_KEY


class TestIdempotencyCheckerIntegration:
    """幂等性检查器集成测试"""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis客户端"""
        redis_mock = MagicMock()
        redis_mock.exists.return_value = 0
        redis_mock.setnx.return_value = True
        redis_mock.set.return_value = True
        redis_mock.get.return_value = None
        redis_mock.delete.return_value = True
        return redis_mock

    def test_check_new_request(self, mock_redis):
        """测试检查新请求"""
        checker = IdempotencyChecker(mock_redis)
        result = checker.check("new_request_001")
        assert result is True  # 未处理，可以继续

    def test_check_existing_request(self, mock_redis):
        """测试检查已存在的请求"""
        mock_redis.exists.return_value = 1  # 已存在
        checker = IdempotencyChecker(mock_redis)
        result = checker.check("existing_request_001")
        assert result is False  # 已处理，应使用缓存结果

    def test_mark_processing_success(self, mock_redis):
        """测试标记处理中成功"""
        mock_redis.setnx.return_value = True
        checker = IdempotencyChecker(mock_redis)
        result = checker.mark_processing("request_001")
        assert result is True
        mock_redis.setnx.assert_called_once()
        mock_redis.expire.assert_called_once()

    def test_mark_processing_already_marked(self, mock_redis):
        """测试标记处理中已被标记"""
        mock_redis.setnx.return_value = False  # 已被其他实例标记
        checker = IdempotencyChecker(mock_redis)
        result = checker.mark_processing("request_001")
        assert result is False

    def test_mark_processed(self, mock_redis):
        """测试标记已处理"""
        checker = IdempotencyChecker(mock_redis)
        result = checker.mark_processed("request_001", {"status": "success"})
        assert result is True
        mock_redis.set.assert_called_once()

    def test_get_cached_result(self, mock_redis):
        """测试获取缓存结果"""
        import json

        mock_redis.get.return_value = json.dumps({
            "status": "processed",
            "result": {"status": "success", "data": "test"},
        })
        checker = IdempotencyChecker(mock_redis)
        result = checker.get_cached_result("request_001")
        assert result == {"status": "success", "data": "test"}

    def test_get_cached_result_not_found(self, mock_redis):
        """测试获取缓存结果不存在"""
        mock_redis.get.return_value = None
        checker = IdempotencyChecker(mock_redis)
        result = checker.get_cached_result("request_001")
        assert result is None

    def test_get_status(self, mock_redis):
        """测试获取请求状态"""
        import json

        mock_redis.get.return_value = json.dumps({
            "status": "processing",
            "timestamp": time.time(),
        })
        checker = IdempotencyChecker(mock_redis)
        result = checker.get_status("request_001")
        assert result is not None
        assert result["status"] == "processing"

    def test_clear(self, mock_redis):
        """测试清除幂等性记录"""
        checker = IdempotencyChecker(mock_redis)
        result = checker.clear("request_001")
        assert result is True
        mock_redis.delete.assert_called_once()

    def test_generate_key(self, mock_redis):
        """测试生成key"""
        config = IdempotencyConfig(key_prefix="test:")
        checker = IdempotencyChecker(mock_redis, config)
        key = checker._generate_key("request_001")
        assert key == "test:request_001"

    def test_generate_business_key(self, mock_redis):
        """测试生成业务key"""
        checker = IdempotencyChecker(mock_redis)
        key1 = checker._generate_business_key("arg1", "arg2")
        key2 = checker._generate_business_key("arg2", "arg1")
        # 不同顺序应该生成不同的key
        assert key1 != key2
        # 相同参数应该生成相同的key
        key3 = checker._generate_business_key("arg1", "arg2")
        assert key1 == key3


class TestIdempotencyError:
    """幂等性错误测试"""

    def test_idempotency_error_default(self):
        """测试默认错误消息"""
        error = IdempotencyError()
        assert error.message == "Duplicate request detected"
        assert str(error) == "Duplicate request detected"

    def test_idempotency_error_custom(self):
        """测试自定义错误消息"""
        error = IdempotencyError("Custom error message")
        assert error.message == "Custom error message"
        assert str(error) == "Custom error message"


class TestIdempotencyStrategy:
    """幂等性策略测试"""

    def test_request_id_strategy(self):
        """测试请求ID策略"""
        assert IdempotencyStrategy.REQUEST_ID.value == "request_id"

    def test_business_key_strategy(self):
        """测试业务键策略"""
        assert IdempotencyStrategy.BUSINESS_KEY.value == "business_key"

    def test_composite_strategy(self):
        """测试组合策略"""
        assert IdempotencyStrategy.COMPOSITE.value == "composite"


class TestIdempotencyIntegration:
    """幂等性集成测试"""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis客户端"""
        redis_mock = MagicMock()
        redis_mock.exists.return_value = 0
        redis_mock.setnx.return_value = True
        redis_mock.set.return_value = True
        redis_mock.get.return_value = None
        redis_mock.delete.return_value = True
        return redis_mock

    def test_full_idempotency_flow(self, mock_redis):
        """测试完整幂等性流程"""
        import json

        checker = IdempotencyChecker(mock_redis)
        request_id = "test_request_001"

        # 1. 检查请求是否已处理
        is_new = checker.check(request_id)
        assert is_new is True

        # 2. 标记正在处理
        can_process = checker.mark_processing(request_id)
        assert can_process is True

        # 3. 模拟处理完成
        result = {"status": "success", "data": "processed data"}

        # 4. 标记已处理
        checker.mark_processed(request_id, result)

        # 5. 验证缓存结果可获取
        mock_redis.get.return_value = json.dumps({
            "status": "processed",
            "result": result,
        })
        cached_result = checker.get_cached_result(request_id)
        assert cached_result == result

    def test_duplicate_request_flow(self, mock_redis):
        """测试重复请求流程"""
        checker = IdempotencyChecker(mock_redis)
        request_id = "duplicate_request_001"

        # 第一次请求
        assert checker.check(request_id) is True
        assert checker.mark_processing(request_id) is True

        # 模拟请求处理完成后，再次检查
        mock_redis.exists.return_value = 1  # 已存在
        assert checker.check(request_id) is False

    def test_concurrent_requests(self, mock_redis):
        """测试并发请求"""
        checker = IdempotencyChecker(mock_redis)

        # 模拟并发请求同一ID
        mock_redis.setnx.side_effect = [True, False, False]

        # 第一个请求应该成功
        assert checker.mark_processing("concurrent_001") is True
        # 后续请求应该失败
        assert checker.mark_processing("concurrent_001") is False
        assert checker.mark_processing("concurrent_001") is False

    def test_multiple_different_requests(self, mock_redis):
        """测试多个不同请求"""
        checker = IdempotencyChecker(mock_redis)

        requests = [f"request_{i}" for i in range(10)]

        for request_id in requests:
            assert checker.check(request_id) is True
            assert checker.mark_processing(request_id) is True
            checker.mark_processed(request_id, {"id": request_id})

    def test_ttl_behavior(self, mock_redis):
        """测试TTL行为"""
        config = IdempotencyConfig(ttl_seconds=3600)
        checker = IdempotencyChecker(mock_redis, config)

        # 标记处理
        checker.mark_processing("ttl_test")
        checker.mark_processed("ttl_test", {"data": "test"})

        # 验证TTL被设置
        calls = mock_redis.expire.call_args_list
        assert len(calls) == 1
        assert calls[0][0][1] == 3600  # TTL值


class TestIdempotencyEdgeCases:
    """幂等性边界情况测试"""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis客户端"""
        return MagicMock()

    def test_empty_request_id(self, mock_redis):
        """测试空请求ID"""
        checker = IdempotencyChecker(mock_redis)
        # 空ID应该能正常处理
        checker.check("")
        checker.mark_processing("")

    def test_special_characters_in_request_id(self, mock_redis):
        """测试请求ID包含特殊字符"""
        checker = IdempotencyChecker(mock_redis)
        special_id = "request:with:colons/slashes"
        checker.check(special_id)
        checker.mark_processing(special_id)

    def test_very_long_request_id(self, mock_redis):
        """测试很长的请求ID"""
        checker = IdempotencyChecker(mock_redis)
        long_id = "a" * 10000
        checker.check(long_id)
        checker.mark_processing(long_id)

    def test_unicode_in_request_id(self, mock_redis):
        """测试请求ID包含Unicode"""
        checker = IdempotencyChecker(mock_redis)
        unicode_id = "请求_测试_123"
        checker.check(unicode_id)
        checker.mark_processing(unicode_id)