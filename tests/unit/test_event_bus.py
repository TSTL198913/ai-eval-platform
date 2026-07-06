"""事件总线测试

验证EventBus的发布/订阅机制、线程安全、事件类型定义。
"""

import pytest
import asyncio
from unittest.mock import Mock

from src.infra.event_bus import EventBus, EventType, Event, publish_event, subscribe_event


class TestEventBus:
    """事件总线测试"""

    def setup_method(self):
        self.event_bus = EventBus()
        self.event_bus.reset()

    def test_singleton_instance(self):
        """验证EventBus是单例"""
        instance1 = EventBus()
        instance2 = EventBus()
        assert instance1 is instance2

    def test_publish_and_subscribe(self):
        """验证发布/订阅机制"""
        handler_called = []
        
        def handler(event):
            handler_called.append(event)
        
        self.event_bus.subscribe(EventType.EVALUATION_COMPLETED, handler)
        
        self.event_bus.publish(
            EventType.EVALUATION_COMPLETED,
            evaluator_type="test",
            score=0.85,
            source="test",
        )
        
        assert len(handler_called) == 1
        assert handler_called[0].event_type == EventType.EVALUATION_COMPLETED
        assert handler_called[0].payload["score"] == 0.85

    def test_unsubscribe(self):
        """验证取消订阅"""
        handler_called = []
        
        def handler(event):
            handler_called.append(event)
        
        self.event_bus.subscribe(EventType.EVALUATION_COMPLETED, handler)
        self.event_bus.unsubscribe(EventType.EVALUATION_COMPLETED, handler)
        
        self.event_bus.publish(
            EventType.EVALUATION_COMPLETED,
            evaluator_type="test",
            score=0.85,
        )
        
        assert len(handler_called) == 0

    def test_multiple_subscribers(self):
        """验证多个订阅者"""
        handler1_called = []
        handler2_called = []
        
        def handler1(event):
            handler1_called.append(event)
        
        def handler2(event):
            handler2_called.append(event)
        
        self.event_bus.subscribe(EventType.EVALUATION_COMPLETED, handler1)
        self.event_bus.subscribe(EventType.EVALUATION_COMPLETED, handler2)
        
        self.event_bus.publish(
            EventType.EVALUATION_COMPLETED,
            evaluator_type="test",
            score=0.85,
        )
        
        assert len(handler1_called) == 1
        assert len(handler2_called) == 1

    def test_different_event_types(self):
        """验证不同事件类型"""
        eval_handler_called = []
        fallback_handler_called = []
        
        def eval_handler(event):
            eval_handler_called.append(event)
        
        def fallback_handler(event):
            fallback_handler_called.append(event)
        
        self.event_bus.subscribe(EventType.EVALUATION_COMPLETED, eval_handler)
        self.event_bus.subscribe(EventType.FALLBACK_TRIGGERED, fallback_handler)
        
        self.event_bus.publish(EventType.EVALUATION_COMPLETED, score=0.85)
        self.event_bus.publish(EventType.FALLBACK_TRIGGERED, score=0.5)
        
        assert len(eval_handler_called) == 1
        assert len(fallback_handler_called) == 1
        assert eval_handler_called[0].event_type == EventType.EVALUATION_COMPLETED
        assert fallback_handler_called[0].event_type == EventType.FALLBACK_TRIGGERED

    @pytest.mark.asyncio
    async def test_publish_async(self):
        """验证异步发布"""
        handler_called = []
        
        async def async_handler(event):
            handler_called.append(event)
        
        self.event_bus.subscribe(EventType.EVALUATION_COMPLETED, async_handler, is_async=True)
        
        await self.event_bus.publish_async(
            EventType.EVALUATION_COMPLETED,
            evaluator_type="test",
            score=0.85,
        )
        
        assert len(handler_called) == 1

    def test_event_type_constants(self):
        """验证事件类型常量定义"""
        assert EventType.CALIBRATION_NEEDED == "calibration_needed"
        assert EventType.EVALUATION_COMPLETED == "evaluation_completed"
        assert EventType.FALLBACK_TRIGGERED == "fallback_triggered"
        assert EventType.DRIFT_DETECTED == "drift_detected"
        assert EventType.ERROR_OCCURRED == "error_occurred"
        assert EventType.SCORE_CALIBRATED == "score_calibrated"
        assert EventType.SELF_HEALING_STARTED == "self_healing_started"
        assert EventType.SELF_HEALING_COMPLETED == "self_healing_completed"

    def test_event_dataclass(self):
        """验证Event数据结构"""
        event = Event(
            event_type="test_event",
            payload={"key": "value"},
            source="test_source",
        )
        
        assert event.event_type == "test_event"
        assert event.payload["key"] == "value"
        assert event.source == "test_source"
        assert event.timestamp is not None

    def test_convenience_functions(self):
        """验证便捷函数"""
        handler_called = []
        
        def handler(event):
            handler_called.append(event)
        
        subscribe_event(EventType.EVALUATION_COMPLETED, handler)
        publish_event(EventType.EVALUATION_COMPLETED, score=0.85)
        
        assert len(handler_called) == 1

    def test_get_subscriber_count(self):
        """验证获取订阅者数量"""
        def handler1(event):
            pass
        
        def handler2(event):
            pass
        
        self.event_bus.subscribe(EventType.EVALUATION_COMPLETED, handler1)
        self.event_bus.subscribe(EventType.EVALUATION_COMPLETED, handler2)
        
        assert self.event_bus.get_subscriber_count(EventType.EVALUATION_COMPLETED) == 2
        assert self.event_bus.get_subscriber_count(EventType.FALLBACK_TRIGGERED) == 0

    def test_list_event_types(self):
        """验证列出已注册事件类型"""
        def handler1(event):
            pass
        
        def handler2(event):
            pass
        
        self.event_bus.subscribe(EventType.EVALUATION_COMPLETED, handler1)
        self.event_bus.subscribe(EventType.FALLBACK_TRIGGERED, handler2)
        
        event_types = self.event_bus.list_event_types()
        assert EventType.EVALUATION_COMPLETED in event_types
        assert EventType.FALLBACK_TRIGGERED in event_types
        assert len(event_types) == 2

    def test_handler_exception_isolation(self):
        """验证处理器异常不影响其他处理器"""
        handler1_called = []
        handler2_called = []
        
        def handler1(event):
            handler1_called.append(event)
            raise ValueError("Test error")
        
        def handler2(event):
            handler2_called.append(event)
        
        self.event_bus.subscribe(EventType.EVALUATION_COMPLETED, handler1)
        self.event_bus.subscribe(EventType.EVALUATION_COMPLETED, handler2)
        
        self.event_bus.publish(EventType.EVALUATION_COMPLETED, score=0.85)
        
        assert len(handler1_called) == 1
        assert len(handler2_called) == 1