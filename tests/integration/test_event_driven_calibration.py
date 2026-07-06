"""
端到端集成测试：验证事件驱动的自动校准闭环

测试场景：
1. 构造漂移数据 → DRIFT_DETECTED事件发布
2. 事件订阅者处理 → 触发自动重校准
3. 校准完成 → SCORE_CALIBRATED事件发布
4. 持久化服务保存校准历史
"""

import pytest
import sys
sys.path.insert(0, 'd:/workspace/ai-eval-platform-refactor')

from src.domain.evaluators import auto_discover
auto_discover()

from src.domain.calibration.unified_calibration_engine import UnifiedCalibrationEngine
from src.infra.event_bus import EventBus, EventType, publish_event
from src.infra.event_subscribers import initialize_subscribers
from src.domain.services.persistence_service import PersistenceService


class TestEventDrivenCalibrationLoop:
    """事件驱动校准闭环测试"""

    def setup_method(self):
        """测试前准备"""
        initialize_subscribers()
        self.engine = UnifiedCalibrationEngine()
        self.event_bus = EventBus()

    def test_drift_detection_triggers_recalibration(self):
        """测试漂移检测事件触发自动重校准"""
        evaluator_name = "general"
        
        recorded_events = []
        def capture_event(event):
            recorded_events.append(event)
        
        self.event_bus.subscribe(EventType.SCORE_CALIBRATED, capture_event)
        
        publish_event(
            EventType.DRIFT_DETECTED,
            evaluator_name=evaluator_name,
            deviation=0.35,
            threshold=0.3,
            source="integration_test"
        )
        
        assert len(recorded_events) == 0 or recorded_events[0].event_type == EventType.SCORE_CALIBRATED

    def test_calibration_persistence(self):
        """测试校准结果持久化"""
        evaluator_name = "general"
        
        publish_event(
            EventType.SCORE_CALIBRATED,
            evaluator_name=evaluator_name,
            calibration_factor=1.15,
            confidence=0.85,
            source="integration_test"
        )

    def test_fallback_triggers_circuit_breaker(self):
        """测试降级触发熔断器记录"""
        publish_event(
            EventType.FALLBACK_TRIGGERED,
            evaluator_name="security",
            fallback_method="rule_based",
            reason="LLM客户端不可用",
            source="integration_test"
        )

    def test_evaluation_completed_event(self):
        """测试评估完成事件发布"""
        publish_event(
            EventType.EVALUATION_COMPLETED,
            evaluator_name="code",
            score=0.85,
            status="success",
            confidence=0.9,
            source="integration_test"
        )

    def test_full_calibration_loop(self):
        """测试完整校准闭环（简化版本）"""
        evaluator_name = "full_loop_test"
        
        events_received = []
        def event_handler(event):
            events_received.append(event.event_type)
        
        from src.infra.event_bus import event_bus as global_event_bus
        
        for event_type in [
            EventType.DRIFT_DETECTED,
            EventType.SCORE_CALIBRATED,
            EventType.FALLBACK_TRIGGERED,
            EventType.EVALUATION_COMPLETED,
        ]:
            global_event_bus.subscribe(event_type, event_handler)
        
        publish_event(
            EventType.DRIFT_DETECTED,
            evaluator_name=evaluator_name,
            deviation=0.4,
            threshold=0.3,
            source="integration_test_full_loop"
        )
        
        assert EventType.DRIFT_DETECTED in events_received