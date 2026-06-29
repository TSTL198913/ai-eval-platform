"""
熔断器单元测试
测试目标：验证 CircuitBreaker 的状态转换逻辑、失败计数、熔断恢复机制
关键发现：
- 熔断器支持 CLOSED -> OPEN -> HALF_OPEN -> CLOSED 状态转换
- 连续失败达到阈值后触发熔断
- 超时后自动进入半开状态，允许探测
- 半开状态下连续成功达到阈值后关闭熔断
"""

import os
import sys
import time
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.distributed.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitState,
)


class TestCircuitBreakerInitialization:
    """初始化测试 - 熔断器初始状态"""

    def test_default_state_is_closed(self):
        """新建熔断器应处于 CLOSED 状态"""
        cb = CircuitBreaker("test", auto_load_redis=False)
        assert cb.state == CircuitState.CLOSED
        assert cb.is_closed is True
        assert cb.is_open is False
        assert cb.is_half_open is False

    def test_default_config_values(self):
        """默认配置值应正确"""
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.success_threshold == 2
        assert config.timeout_seconds == 30.0
        assert config.half_open_max_calls == 3

    def test_custom_config_applied(self):
        """自定义配置应被正确应用"""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=1,
            timeout_seconds=10.0,
            half_open_max_calls=5,
        )
        cb = CircuitBreaker("test_custom", config=config, auto_load_redis=False)
        assert cb.config.failure_threshold == 3
        assert cb.config.success_threshold == 1
        assert cb.config.timeout_seconds == 10.0

    def test_initial_stats_are_zero(self):
        """初始统计数据应为零"""
        cb = CircuitBreaker("test_stats", auto_load_redis=False)
        assert cb.stats.total_calls == 0
        assert cb.stats.successful_calls == 0
        assert cb.stats.failed_calls == 0
        assert cb.stats.rejected_calls == 0
        assert cb.stats.state_changes == 0


class TestCircuitBreakerClosedState:
    """CLOSED 状态测试 - 正常流量通过"""

    def test_successful_call_increments_stats(self):
        """成功调用应更新成功计数"""
        cb = CircuitBreaker("test_success", auto_load_redis=False)
        result = cb.call_sync(lambda: "ok")
        assert result == "ok"
        assert cb.stats.total_calls == 1
        assert cb.stats.successful_calls == 1
        assert cb.stats.failed_calls == 0
        assert cb.is_closed is True

    def test_failed_call_increments_failure_count(self):
        """失败调用应增加失败计数"""
        cb = CircuitBreaker("test_failure", auto_load_redis=False)
        with pytest.raises(ValueError):
            cb.call_sync(lambda: (_ for _ in ()).throw(ValueError("test error")))
        assert cb.stats.total_calls == 1
        assert cb.stats.failed_calls == 1
        assert cb.is_closed is True  # 未达到阈值，仍为 CLOSED

    def test_multiple_failures_before_threshold(self):
        """阈值以下的失败不应触发熔断"""
        config = CircuitBreakerConfig(failure_threshold=5)
        cb = CircuitBreaker("test_threshold", config=config, auto_load_redis=False)

        for i in range(4):
            with pytest.raises(ValueError):
                error_msg = f"error {i}"
                cb.call_sync(lambda msg=error_msg: (_ for _ in ()).throw(ValueError(msg)))

        assert cb.is_closed is True
        assert cb.stats.failed_calls == 4

    def test_failure_threshold_triggers_open(self):
        """达到失败阈值应触发熔断（OPEN 状态）"""
        config = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker("test_open", config=config, auto_load_redis=False)

        for i in range(3):
            with pytest.raises(ValueError):
                error_msg = f"error {i}"
                cb.call_sync(lambda msg=error_msg: (_ for _ in ()).throw(ValueError(msg)))

        assert cb.is_open is True
        assert cb.state == CircuitState.OPEN
        assert cb.stats.state_changes == 1


class TestCircuitBreakerOpenState:
    """OPEN 状态测试 - 熔断时快速失败"""

    def test_open_state_rejects_calls(self):
        """熔断状态下应拒绝调用并抛出 CircuitBreakerError"""
        config = CircuitBreakerConfig(failure_threshold=2)
        cb = CircuitBreaker("test_reject", config=config, auto_load_redis=False)

        # 触发熔断
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call_sync(lambda: (_ for _ in ()).throw(ValueError("fail")))

        assert cb.is_open is True

        # 熔断后调用应被拒绝
        with pytest.raises(CircuitBreakerError) as exc_info:
            cb.call_sync(lambda: "should not be called")

        assert "OPEN" in str(exc_info.value)
        assert cb.stats.rejected_calls == 1

    def test_success_resets_failure_count(self):
        """成功调用应重置失败计数"""
        config = CircuitBreakerConfig(failure_threshold=5)
        cb = CircuitBreaker("test_reset", config=config, auto_load_redis=False)

        # 2次失败
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call_sync(lambda: (_ for _ in ()).throw(ValueError("fail")))

        # 1次成功
        cb.call_sync(lambda: "ok")

        # 失败计数应被重置
        # 再失败4次仍不应熔断（因为成功后重置了）
        for _ in range(4):
            with pytest.raises(ValueError):
                cb.call_sync(lambda: (_ for _ in ()).throw(ValueError("fail")))

        assert cb.is_closed is True  # 4 < 5，仍未熔断


class TestCircuitBreakerHalfOpenState:
    """HALF_OPEN 状态测试 - 熔断恢复探测"""

    def test_timeout_transitions_to_half_open(self):
        """超时后应自动进入半开状态"""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            timeout_seconds=0.1,  # 很短的超时便于测试
        )
        cb = CircuitBreaker("test_half_open", config=config, auto_load_redis=False)

        # 触发熔断
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call_sync(lambda: (_ for _ in ()).throw(ValueError("fail")))

        assert cb.is_open is True

        # 等待超时
        time.sleep(0.15)

        # 状态应自动转为 HALF_OPEN
        assert cb.is_half_open is True

    def test_half_open_success_closes_circuit(self):
        """半开状态下连续成功应关闭熔断"""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            success_threshold=2,
            timeout_seconds=0.1,
        )
        cb = CircuitBreaker("test_recovery", config=config, auto_load_redis=False)

        # 触发熔断
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call_sync(lambda: (_ for _ in ()).throw(ValueError("fail")))

        # 等待进入半开
        time.sleep(0.15)
        assert cb.is_half_open is True

        # 连续成功应关闭熔断
        cb.call_sync(lambda: "ok1")
        cb.call_sync(lambda: "ok2")

        assert cb.is_closed is True
        assert cb.stats.state_changes == 3  # CLOSED->OPEN, OPEN->HALF_OPEN, HALF_OPEN->CLOSED

    def test_half_open_failure_reopens_circuit(self):
        """半开状态下失败应重新打开熔断"""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            success_threshold=2,
            timeout_seconds=0.1,
        )
        cb = CircuitBreaker("test_reopen", config=config, auto_load_redis=False)

        # 触发熔断
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call_sync(lambda: (_ for _ in ()).throw(ValueError("fail")))

        # 等待进入半开
        time.sleep(0.15)
        assert cb.is_half_open is True

        # 半开状态下失败应重新熔断
        with pytest.raises(ValueError):
            cb.call_sync(lambda: (_ for _ in ()).throw(ValueError("fail again")))

        assert cb.is_open is True

    def test_half_open_max_calls_limit(self):
        """半开状态下超过最大探测调用数应拒绝"""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            success_threshold=5,
            timeout_seconds=0.1,
            half_open_max_calls=2,
        )
        cb = CircuitBreaker("test_max_calls", config=config, auto_load_redis=False)

        # 触发熔断
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call_sync(lambda: (_ for _ in ()).throw(ValueError("fail")))

        # 等待进入半开
        time.sleep(0.15)
        assert cb.is_half_open is True

        # 2次成功调用（达到 half_open_max_calls）
        cb.call_sync(lambda: "ok1")
        cb.call_sync(lambda: "ok2")

        # 第3次应被拒绝
        with pytest.raises(CircuitBreakerError) as exc_info:
            cb.call_sync(lambda: "should be rejected")

        assert "HALF_OPEN" in str(exc_info.value)
        assert "max calls" in str(exc_info.value).lower()


class TestCircuitBreakerStats:
    """统计数据测试"""

    def test_stats_track_all_metrics(self):
        """统计应正确追踪所有指标"""
        cb = CircuitBreaker("test_metrics", auto_load_redis=False)

        # 3次成功
        for _ in range(3):
            cb.call_sync(lambda: "ok")

        # 2次失败
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call_sync(lambda: (_ for _ in ()).throw(ValueError("fail")))

        assert cb.stats.total_calls == 5
        assert cb.stats.successful_calls == 3
        assert cb.stats.failed_calls == 2
        assert cb.stats.rejected_calls == 0
        assert cb.stats.state_changes == 0

    def test_state_change_tracking(self):
        """状态转换次数应正确统计"""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            success_threshold=1,
            timeout_seconds=0.1,
        )
        cb = CircuitBreaker("test_state_changes", config=config, auto_load_redis=False)

        # CLOSED -> OPEN
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call_sync(lambda: (_ for _ in ()).throw(ValueError("fail")))

        assert cb.stats.state_changes == 1

        # OPEN -> HALF_OPEN (通过 property 访问触发)
        time.sleep(0.15)
        _ = cb.is_half_open  # 触发状态转换检查

        # HALF_OPEN -> CLOSED
        cb.call_sync(lambda: "recovery")

        # 至少有3次状态转换
        assert cb.stats.state_changes >= 2


class TestCircuitBreakerEdgeCases:
    """边界场景测试"""

    def test_empty_function_works(self):
        """空函数应正常执行"""
        cb = CircuitBreaker("test_empty", auto_load_redis=False)
        result = cb.call_sync(lambda: None)
        assert result is None

    def test_exception_propagates(self):
        """异常应原样传播"""
        cb = CircuitBreaker("test_propagate", auto_load_redis=False)

        class CustomError(Exception):
            pass

        with pytest.raises(CustomError):
            cb.call_sync(lambda: (_ for _ in ()).throw(CustomError("custom")))

    def test_function_arguments_passed(self):
        """函数参数应正确传递"""
        cb = CircuitBreaker("test_args", auto_load_redis=False)

        def add(a, b):
            return a + b

        result = cb.call_sync(add, 3, 4)
        assert result == 7

    def test_function_keyword_arguments_passed(self):
        """关键字参数应正确传递"""
        cb = CircuitBreaker("test_kwargs", auto_load_redis=False)

        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}!"

        result = cb.call_sync(greet, "World", greeting="Hi")
        assert result == "Hi, World!"


class TestCircuitBreakerWithRedisMock:
    """Redis 持久化测试（使用 Mock）"""

    def test_init_with_redis_mock(self):
        """使用 Mock Redis 客户端初始化应正常"""
        mock_redis = MagicMock()
        mock_redis.get.return_value = None  # 无历史数据

        cb = CircuitBreaker("test_redis", redis_client=mock_redis)
        assert cb.is_closed is True

    def test_state_saved_to_redis_on_transition(self):
        """状态转换时应保存到 Redis"""
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_redis.get_circuit_breaker_state.return_value = None

        failure_count = 0

        def increment_counter(name):
            nonlocal failure_count
            failure_count += 1
            return failure_count

        mock_redis.increment_failure_count.side_effect = increment_counter

        config = CircuitBreakerConfig(failure_threshold=2)
        cb = CircuitBreaker("test_redis_save", config=config, redis_client=mock_redis)

        # 触发熔断
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call_sync(lambda: (_ for _ in ()).throw(ValueError("fail")))

        # 应调用 Redis set_circuit_breaker_state 保存状态
        assert mock_redis.set_circuit_breaker_state.called
        call_args = mock_redis.set_circuit_breaker_state.call_args
        assert "test_redis_save" in call_args[0][0]
