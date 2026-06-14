"""测试 distributed/idempotency.py - 幂等性保障模块"""

import json
import time
from unittest.mock import Mock

import pytest

from src.distributed.idempotency import (
    IdempotencyChecker,
    IdempotencyConfig,
    IdempotencyError,
    IdempotencyStrategy,
    idempotent,
)


class TestIdempotencyConfig:
    """测试幂等性配置"""

    def test_default_config(self):
        config = IdempotencyConfig()
        assert config.ttl_seconds == 3600
        assert config.key_prefix == "idempotency:"
        assert config.strategy == IdempotencyStrategy.REQUEST_ID

    def test_custom_config(self):
        config = IdempotencyConfig(
            ttl_seconds=7200,
            key_prefix="custom:",
            strategy=IdempotencyStrategy.BUSINESS_KEY,
        )
        assert config.ttl_seconds == 7200
        assert config.key_prefix == "custom:"
        assert config.strategy == IdempotencyStrategy.BUSINESS_KEY


class TestIdempotencyChecker:
    """测试幂等性检查器"""

    @pytest.fixture
    def mock_redis(self):
        redis = Mock()
        redis.exists.return_value = 0
        redis.setnx.return_value = 1
        redis.set = Mock()
        redis.get.return_value = None
        redis.expire = Mock()
        redis.delete = Mock()
        return redis

    @pytest.fixture
    def checker(self, mock_redis):
        return IdempotencyChecker(mock_redis)

    def test_check_new_request(self, checker, mock_redis):
        """测试新请求检查"""
        mock_redis.exists.return_value = 0

        result = checker.check("req-001")
        assert result is True
        mock_redis.exists.assert_called_with("idempotency:req-001")

    def test_check_duplicate_request(self, checker, mock_redis):
        """测试重复请求检查"""
        mock_redis.exists.return_value = 1

        result = checker.check("req-001")
        assert result is False

    def test_mark_processing(self, checker, mock_redis):
        """测试标记正在处理"""
        result = checker.mark_processing("req-001")
        assert result == 1  # setnx 返回整数 1 表示成功
        mock_redis.setnx.assert_called()
        mock_redis.expire.assert_called()

    def test_mark_processing_conflict(self, checker, mock_redis):
        """测试标记冲突"""
        mock_redis.setnx.return_value = 0

        result = checker.mark_processing("req-001")
        assert result == 0  # setnx 返回整数 0 表示失败

    def test_mark_processed(self, checker, mock_redis):
        """测试标记已处理"""
        checker.mark_processed("req-001", result={"status": "success"}, metadata={"model": "gpt4"})
        mock_redis.set.assert_called()

        # 验证保存的数据
        call_args = mock_redis.set.call_args
        saved_data = json.loads(call_args[0][1])
        assert saved_data["status"] == "processed"
        assert saved_data["result"]["status"] == "success"

    def test_get_cached_result(self, checker, mock_redis):
        """测试获取缓存结果"""
        mock_redis.get.return_value = json.dumps(
            {
                "status": "processed",
                "result": {"score": 0.95},
                "timestamp": time.time(),
            }
        )

        result = checker.get_cached_result("req-001")
        assert result["score"] == 0.95

    def test_get_cached_result_not_processed(self, checker, mock_redis):
        """测试获取缓存结果（未处理状态）"""
        mock_redis.get.return_value = json.dumps(
            {
                "status": "processing",
                "timestamp": time.time(),
            }
        )

        result = checker.get_cached_result("req-001")
        assert result is None

    def test_get_cached_result_not_found(self, checker, mock_redis):
        """测试获取缓存结果（不存在）"""
        mock_redis.get.return_value = None

        result = checker.get_cached_result("req-001")
        assert result is None

    def test_get_status(self, checker, mock_redis):
        """测试获取状态"""
        mock_redis.get.return_value = json.dumps(
            {
                "status": "processing",
                "timestamp": 1000.0,
            }
        )

        status = checker.get_status("req-001")
        assert status["status"] == "processing"
        assert status["timestamp"] == 1000.0

    def test_clear(self, checker, mock_redis):
        """测试清除记录"""
        checker.clear("req-001")
        mock_redis.delete.assert_called_with("idempotency:req-001")


class TestIdempotentDecorator:
    """测试幂等性装饰器"""

    @pytest.fixture
    def mock_redis(self):
        redis = Mock()
        redis.exists.return_value = 0
        redis.setnx.return_value = 1
        redis.set = Mock()
        redis.get.return_value = None
        redis.expire = Mock()
        redis.delete = Mock()
        return redis

    async def test_decorator_success(self, mock_redis):
        """测试装饰器成功执行"""

        @idempotent(mock_redis)
        async def process_request(request_id: str):
            return {"result": "success"}

        result = await process_request("req-001")
        assert result["result"] == "success"
        mock_redis.set.assert_called()

    async def test_decorator_duplicate_cached(self, mock_redis):
        """测试装饰器重复请求返回缓存"""
        mock_redis.exists.return_value = 1
        mock_redis.get.return_value = json.dumps(
            {
                "status": "processed",
                "result": {"result": "cached"},
            }
        )

        @idempotent(mock_redis)
        async def process_request(request_id: str):
            return {"result": "new"}

        result = await process_request("req-001")
        assert result["result"] == "cached"

    async def test_decorator_duplicate_processing(self, mock_redis):
        """测试装饰器重复请求正在处理"""
        mock_redis.exists.return_value = 1
        mock_redis.get.return_value = json.dumps(
            {
                "status": "processing",
            }
        )

        @idempotent(mock_redis)
        async def process_request(request_id: str):
            return {"result": "success"}

        with pytest.raises(IdempotencyError):
            await process_request("req-001")

    async def test_decorator_failure_clears(self, mock_redis):
        """测试装饰器失败时清除标记"""
        mock_redis.setnx.return_value = 1

        @idempotent(mock_redis)
        async def process_request(request_id: str):
            raise ValueError("Processing failed")

        with pytest.raises(ValueError):
            await process_request("req-001")

        # 失败时应清除标记
        mock_redis.delete.assert_called()

    async def test_decorator_with_key_extractor(self, mock_redis):
        """测试装饰器使用自定义 key 提取器"""

        @idempotent(mock_redis, key_extractor=lambda req: req["id"])
        async def process_request(request: dict):
            return {"result": "success"}

        result = await process_request({"id": "custom-001", "data": "test"})
        assert result["result"] == "success"
