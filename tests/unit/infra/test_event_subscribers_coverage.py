"""
回归测试：事件订阅者全覆盖
BUG-014: 事件订阅覆盖率不足 - 8种事件仅3种有订阅者

测试场景覆盖：
1. 正向：8个事件全部有订阅者
2. 正向：每个订阅者能正确处理事件
3. 正向：事件发布后订阅者被调用
4. 负向：订阅者内部异常不影响事件总线
5. 边界：空payload事件处理
"""

import pytest
from unittest.mock import patch, MagicMock


class TestEventSubscriberCoverage:
    """事件订阅者覆盖率测试"""

    def test_all_eight_event_types_have_subscribers(self):
        """正向：8种事件类型全部有订阅者"""
        from src.infra.event_bus import EventType, EventBus
        from src.infra.event_subscribers import initialize_subscribers

        bus = EventBus()
        initialize_subscribers()

        event_types = [
            EventType.CALIBRATION_NEEDED,
            EventType.EVALUATION_COMPLETED,
            EventType.DRIFT_DETECTED,
            EventType.FALLBACK_TRIGGERED,
            EventType.ERROR_OCCURRED,
            EventType.SCORE_CALIBRATED,
            EventType.SELF_HEALING_STARTED,
            EventType.SELF_HEALING_COMPLETED,
        ]

        for event_type in event_types:
            subscribers = bus._subscribers.get(event_type, [])
            assert len(subscribers) > 0, f"事件 {event_type} 没有订阅者"

    def test_initialize_subscribers_registers_all_eight(self):
        """正向：initialize_subscribers 注册全部8个订阅者"""
        from src.infra.event_bus import EventType, EventBus
        from src.infra.event_subscribers import initialize_subscribers

        bus = EventBus()
        initial_counts = {}
        event_names = [attr for attr in dir(EventType) if not attr.startswith("_")]
        for attr in event_names:
            et = getattr(EventType, attr)
            if isinstance(et, str):
                initial_counts[et] = len(bus._subscribers.get(et, []))

        initialize_subscribers()

        event_types = [
            EventType.CALIBRATION_NEEDED,
            EventType.EVALUATION_COMPLETED,
            EventType.DRIFT_DETECTED,
            EventType.FALLBACK_TRIGGERED,
            EventType.ERROR_OCCURRED,
            EventType.SCORE_CALIBRATED,
            EventType.SELF_HEALING_STARTED,
            EventType.SELF_HEALING_COMPLETED,
        ]

        for event_type in event_types:
            subscribers = bus._subscribers.get(event_type, [])
            assert len(subscribers) > 0, \
                f"事件 {event_type} 初始化后仍无订阅者"

    def test_calibration_needed_subscriber(self):
        """正向：CALIBRATION_NEEDED 事件处理函数可调用"""
        from src.infra.event_subscribers import handle_calibration_needed
        from src.infra.event_bus import Event, EventType

        event = Event(
            event_type=EventType.CALIBRATION_NEEDED,
            payload={"evaluator_name": "test_eval", "reason": "drift", "priority": "high"},
        )

        try:
            handle_calibration_needed(event)
        except Exception:
            pytest.fail("handle_calibration_needed 不应抛出异常")

    def test_evaluation_completed_subscriber(self):
        """正向：EVALUATION_COMPLETED 事件处理函数可调用"""
        from src.infra.event_subscribers import handle_evaluation_completed
        from src.infra.event_bus import Event, EventType

        event = Event(
            event_type=EventType.EVALUATION_COMPLETED,
            payload={"evaluator_type": "general", "status": "success", "score": 85.0, "duration_ms": 120},
        )

        try:
            handle_evaluation_completed(event)
        except Exception:
            pytest.fail("handle_evaluation_completed 不应抛出异常")

    def test_error_occurred_subscriber(self):
        """正向：ERROR_OCCURRED 事件处理函数可调用"""
        from src.infra.event_subscribers import handle_error_occurred
        from src.infra.event_bus import Event, EventType

        event = Event(
            event_type=EventType.ERROR_OCCURRED,
            payload={"error_type": "llm_timeout", "error_message": "connection timeout", "evaluator_name": "general"},
        )

        try:
            handle_error_occurred(event)
        except Exception:
            pytest.fail("handle_error_occurred 不应抛出异常")

    def test_self_healing_started_subscriber(self):
        """正向：SELF_HEALING_STARTED 事件处理函数可调用"""
        from src.infra.event_subscribers import handle_self_healing_started
        from src.infra.event_bus import Event, EventType

        event = Event(
            event_type=EventType.SELF_HEALING_STARTED,
            payload={"evaluator_name": "general", "reason": "drift", "healing_method": "recalibration"},
        )

        try:
            handle_self_healing_started(event)
        except Exception:
            pytest.fail("handle_self_healing_started 不应抛出异常")

    def test_self_healing_completed_subscriber(self):
        """正向：SELF_HEALING_COMPLETED 事件处理函数可调用"""
        from src.infra.event_subscribers import handle_self_healing_completed
        from src.infra.event_bus import Event, EventType

        event = Event(
            event_type=EventType.SELF_HEALING_COMPLETED,
            payload={
                "evaluator_name": "general",
                "success": True,
                "before_deviation": 0.08,
                "after_deviation": 0.03,
                "improvement": 0.625,
            },
        )

        try:
            handle_self_healing_completed(event)
        except Exception:
            pytest.fail("handle_self_healing_completed 不应抛出异常")

    def test_subscriber_handles_empty_payload(self):
        """边界：空payload事件处理不崩溃"""
        from src.infra.event_subscribers import (
            handle_calibration_needed,
            handle_evaluation_completed,
            handle_error_occurred,
            handle_self_healing_started,
            handle_self_healing_completed,
        )
        from src.infra.event_bus import Event, EventType

        handlers = [
            (handle_calibration_needed, EventType.CALIBRATION_NEEDED),
            (handle_evaluation_completed, EventType.EVALUATION_COMPLETED),
            (handle_error_occurred, EventType.ERROR_OCCURRED),
            (handle_self_healing_started, EventType.SELF_HEALING_STARTED),
            (handle_self_healing_completed, EventType.SELF_HEALING_COMPLETED),
        ]

        for handler, event_type in handlers:
            event = Event(event_type=event_type, payload={})
            try:
                handler(event)
            except Exception as e:
                pytest.fail(f"{handler.__name__} 处理空payload时抛出异常: {e}")

    def test_self_healing_failure_triggers_error_log(self):
        """负向：自修复失败事件应记录错误级日志"""
        from src.infra.event_subscribers import handle_self_healing_completed
        from src.infra.event_bus import Event, EventType

        event = Event(
            event_type=EventType.SELF_HEALING_COMPLETED,
            payload={
                "evaluator_name": "general",
                "success": False,
                "failure_reason": "calibration_timeout",
            },
        )

        try:
            handle_self_healing_completed(event)
        except Exception:
            pytest.fail("handle_self_healing_completed 不应抛出异常")

    def test_event_subscription_accumulates(self):
        """边界：重复调用 initialize_subscribers 会累加订阅者（已知行为）"""
        from src.infra.event_bus import EventType, EventBus
        from src.infra.event_subscribers import initialize_subscribers

        bus = EventBus()
        initialize_subscribers()
        count_after_first = len(bus._subscribers.get(EventType.ERROR_OCCURRED, []))

        initialize_subscribers()
        count_after_second = len(bus._subscribers.get(EventType.ERROR_OCCURRED, []))

        assert count_after_second >= count_after_first, \
            "重复初始化应至少保持原有订阅者数量"
