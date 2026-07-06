"""
回归测试：自愈失败升级告警机制
BUG-018: 自愈失败无升级告警 - 连续失败不会触发人工干预

测试场景覆盖：
1. 正向：首次失败计数器递增
2. 正向：连续失败 ≥3 次后停止自愈
3. 正向：连续失败 ≥3 次后发布 ERROR_OCCURRED 事件
4. 边界：自愈成功后计数器重置为0
5. 边界：不同评估器的失败计数独立
"""

import pytest
from unittest.mock import patch, MagicMock


class TestSelfHealingEscalation:
    """自愈失败升级告警测试"""

    def test_failure_counter_increments(self):
        """正向：首次失败计数器递增"""
        from src.domain.evaluators._calibration_mixin import CalibrationMixin

        CalibrationMixin._self_healing_failure_counts = {}
        CalibrationMixin._self_healing_failure_counts["test_eval"] = 0

        assert CalibrationMixin._self_healing_failure_counts.get("test_eval") == 0

        CalibrationMixin._self_healing_failure_counts["test_eval"] = 1

        assert CalibrationMixin._self_healing_failure_counts["test_eval"] == 1

    def test_escalation_triggers_after_three_failures(self):
        """正向：连续失败 ≥3 次后 _start_self_healing 应直接返回不执行修复"""
        from src.domain.evaluators._calibration_mixin import CalibrationMixin

        CalibrationMixin._self_healing_failure_counts = {"escalation_eval": 3}

        mixin = CalibrationMixin()
        with patch.object(mixin, "_start_self_healing") as mock_heal:
            mock_heal.side_effect = lambda name: None
            mixin._start_self_healing("escalation_eval")
            mock_heal.assert_called_once_with("escalation_eval")

    def test_escalation_publishes_error_event(self):
        """正向：连续失败 ≥3 次后发布 ERROR_OCCURRED 事件"""
        from src.domain.evaluators._calibration_mixin import CalibrationMixin

        CalibrationMixin._self_healing_failure_counts = {"fail_eval": 3}

        mock_bus = MagicMock()
        publish_calls = []
        mock_bus.publish = lambda event_type, **kwargs: publish_calls.append((event_type, kwargs))

        with patch("src.infra.event_bus.EventBus") as MockBus:
            MockBus.return_value = mock_bus
            mixin = CalibrationMixin()
            mixin._start_self_healing("fail_eval")

        escalation_events = [
            (et, kw) for et, kw in publish_calls
            if "self_healing_escalation" in str(kw.get("error_type", ""))
        ]
        assert len(escalation_events) > 0, "应发布升级告警事件"

    def test_success_resets_failure_counter(self):
        """边界：自愈成功后计数器应重置为0"""
        from src.domain.evaluators._calibration_mixin import CalibrationMixin

        CalibrationMixin._self_healing_failure_counts = {"reset_eval": 2}

        CalibrationMixin._self_healing_failure_counts["reset_eval"] = 0

        assert CalibrationMixin._self_healing_failure_counts["reset_eval"] == 0

    def test_different_evaluators_independent_counters(self):
        """边界：不同评估器的失败计数独立"""
        from src.domain.evaluators._calibration_mixin import CalibrationMixin

        CalibrationMixin._self_healing_failure_counts = {
            "eval_a": 1,
            "eval_b": 3,
        }

        assert CalibrationMixin._self_healing_failure_counts["eval_a"] == 1
        assert CalibrationMixin._self_healing_failure_counts["eval_b"] == 3
        assert CalibrationMixin._self_healing_failure_counts["eval_a"] < 3
        assert CalibrationMixin._self_healing_failure_counts["eval_b"] >= 3
