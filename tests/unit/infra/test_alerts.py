"""测试 AlertService 告警规则服务"""

import pytest


class TestAlertService:
    """测试告警服务"""

    def test_get_rules(self):
        """获取所有告警规则"""
        from src.infra.monitoring.alerts import alert_service

        rules = alert_service.get_rules()
        assert len(rules) > 0

    def test_get_rule(self):
        """获取指定告警规则"""
        from src.infra.monitoring.alerts import alert_service

        rule = alert_service.get_rule("evaluation_latency_high")
        assert rule is not None
        assert rule.name == "evaluation_latency_high"

    def test_add_and_remove_rule(self):
        """添加和删除告警规则"""
        from src.infra.monitoring.alerts import AlertRule, AlertLevel, AlertChannel, alert_service

        new_rule = AlertRule(
            name="test_rule",
            metric_name="test_metric",
            condition=lambda x: x > 100,
            level=AlertLevel.WARN,
            channels=[AlertChannel.LOG],
            description="测试规则",
        )

        alert_service.add_rule(new_rule)
        rule = alert_service.get_rule("test_rule")
        assert rule is not None

        alert_service.remove_rule("test_rule")
        rule = alert_service.get_rule("test_rule")
        assert rule is None

    def test_check_alerts(self):
        """检查告警规则"""
        from src.infra.monitoring.alerts import alert_service

        alerts = alert_service.check_alerts()
        assert isinstance(alerts, list)

    def test_get_alerts(self):
        """获取告警历史"""
        from src.infra.monitoring.alerts import alert_service

        alerts = alert_service.get_alerts()
        assert isinstance(alerts, list)

    def test_clear_alerts(self):
        """清空告警历史"""
        from src.infra.monitoring.alerts import alert_service

        alert_service.clear_alerts()
        alerts = alert_service.get_alerts()
        assert len(alerts) == 0

    def test_get_alert_summary(self):
        """获取告警汇总"""
        from src.infra.monitoring.alerts import alert_service

        summary = alert_service.get_alert_summary()
        assert "info" in summary
        assert "warn" in summary
        assert "error" in summary
        assert "critical" in summary

    def test_alert_level_enum(self):
        """测试告警级别枚举"""
        from src.infra.monitoring.alerts import AlertLevel

        assert AlertLevel.INFO.value == "info"
        assert AlertLevel.WARN.value == "warn"
        assert AlertLevel.ERROR.value == "error"
        assert AlertLevel.CRITICAL.value == "critical"

    def test_alert_channel_enum(self):
        """测试告警渠道枚举"""
        from src.infra.monitoring.alerts import AlertChannel

        assert AlertChannel.LOG.value == "log"
        assert AlertChannel.EMAIL.value == "email"
        assert AlertChannel.DINGTALK.value == "dingtalk"
        assert AlertChannel.FEISHU.value == "feishu"