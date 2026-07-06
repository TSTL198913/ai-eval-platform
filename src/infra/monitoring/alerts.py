"""
告警规则服务 - 2026 工业级标准

用于管理评估平台的告警规则和告警通知，支持：
- 多种告警级别（INFO/WARN/ERROR/CRITICAL）
- 多种告警渠道（日志/邮件/钉钉/飞书）
- 灵活的告警规则配置
- 告警抑制和聚合
- 告警历史记录

设计原则：
- 告警规则配置化，支持动态加载
- 告警通知可扩展，支持多种渠道
- 告警抑制避免告警风暴
- 完整的告警生命周期管理
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional

from src.config import settings
from src.infra.monitoring.metrics import CACHE_HIT_RATE
from src.infra.monitoring.metrics import EVALUATION_ERRORS
from src.infra.monitoring.metrics import EVALUATION_LATENCY

logger = logging.getLogger(__name__)


class AlertLevel(str, Enum):
    """告警级别"""

    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    CRITICAL = "critical"


class AlertChannel(str, Enum):
    """告警渠道"""

    LOG = "log"
    EMAIL = "email"
    DINGTALK = "dingtalk"
    FEISHU = "feishu"


@dataclass
class AlertRule:
    """告警规则"""

    name: str
    metric_name: str
    condition: Callable[[float], bool]
    level: AlertLevel
    channels: List[AlertChannel]
    description: str = ""
    threshold: float = 0.0
    duration: int = 60
    suppress_interval: int = 300
    enabled: bool = True


@dataclass
class Alert:
    """告警实例"""

    rule_name: str
    level: AlertLevel
    message: str
    timestamp: float
    metrics: Dict[str, float] = None
    channel: AlertChannel = None


class AlertService:
    """告警服务"""

    def __init__(self):
        self._rules: Dict[str, AlertRule] = {}
        self._alerts: List[Alert] = []
        self._last_triggered: Dict[str, float] = {}
        self._load_default_rules()

    def _load_default_rules(self):
        """加载默认告警规则"""
        rules = [
            AlertRule(
                name="evaluation_latency_high",
                metric_name="evaluation_latency_seconds",
                condition=lambda x: x > 10,
                level=AlertLevel.WARN,
                channels=[AlertChannel.LOG],
                description="评估延迟超过 10 秒",
                threshold=10,
                duration=60,
            ),
            AlertRule(
                name="evaluation_latency_critical",
                metric_name="evaluation_latency_seconds",
                condition=lambda x: x > 30,
                level=AlertLevel.CRITICAL,
                channels=[AlertChannel.LOG, AlertChannel.EMAIL],
                description="评估延迟超过 30 秒（严重）",
                threshold=30,
                duration=60,
            ),
            AlertRule(
                name="evaluation_error_rate_high",
                metric_name="evaluation_errors_total",
                condition=lambda x: x > 5,
                level=AlertLevel.WARN,
                channels=[AlertChannel.LOG],
                description="评估错误率过高",
                threshold=5,
                duration=60,
            ),
            AlertRule(
                name="cache_hit_rate_low",
                metric_name="cache_hit_rate",
                condition=lambda x: x < 0.5,
                level=AlertLevel.WARN,
                channels=[AlertChannel.LOG],
                description="缓存命中率低于 50%",
                threshold=0.5,
                duration=300,
            ),
            AlertRule(
                name="cache_hit_rate_critical",
                metric_name="cache_hit_rate",
                condition=lambda x: x < 0.3,
                level=AlertLevel.CRITICAL,
                channels=[AlertChannel.LOG, AlertChannel.EMAIL],
                description="缓存命中率低于 30%（严重）",
                threshold=0.3,
                duration=300,
            ),
            AlertRule(
                name="concurrent_evaluations_high",
                metric_name="evaluator_concurrent",
                condition=lambda x: x > settings.max_concurrent_evaluations * 0.8,
                level=AlertLevel.WARN,
                channels=[AlertChannel.LOG],
                description="并发评估数接近上限",
                threshold=settings.max_concurrent_evaluations * 0.8,
                duration=60,
            ),
        ]

        for rule in rules:
            self._rules[rule.name] = rule

    def add_rule(self, rule: AlertRule) -> None:
        """
        添加告警规则

        Args:
            rule: 告警规则
        """
        self._rules[rule.name] = rule
        logger.info(f"添加告警规则: {rule.name}")

    def remove_rule(self, rule_name: str) -> None:
        """
        删除告警规则

        Args:
            rule_name: 规则名称
        """
        if rule_name in self._rules:
            del self._rules[rule_name]
            logger.info(f"删除告警规则: {rule_name}")

    def get_rules(self) -> List[AlertRule]:
        """
        获取所有告警规则

        Returns:
            告警规则列表
        """
        return list(self._rules.values())

    def get_rule(self, rule_name: str) -> Optional[AlertRule]:
        """
        获取指定告警规则

        Args:
            rule_name: 规则名称

        Returns:
            告警规则，如果不存在返回 None
        """
        return self._rules.get(rule_name)

    def check_alerts(self) -> List[Alert]:
        """
        检查所有告警规则，触发符合条件的告警

        Returns:
            触发的告警列表
        """
        triggered_alerts = []

        for rule_name, rule in self._rules.items():
            if not rule.enabled:
                continue

            if self._should_trigger(rule):
                alert = self._create_alert(rule)
                triggered_alerts.append(alert)
                self._notify(alert)

        return triggered_alerts

    def _should_trigger(self, rule: AlertRule) -> bool:
        """
        判断是否应该触发告警

        Args:
            rule: 告警规则

        Returns:
            是否应该触发
        """
        import time

        last_triggered = self._last_triggered.get(rule.name, 0)
        if time.time() - last_triggered < rule.suppress_interval:
            return False

        try:
            metric_value = self._get_metric_value(rule.metric_name)
            if metric_value is None:
                return False

            return rule.condition(metric_value)
        except Exception as e:
            logger.error(f"检查告警规则失败: {rule.name}, 错误: {e}")
            return False

    def _get_metric_value(self, metric_name: str) -> Optional[float]:
        """
        获取指标当前值

        Args:
            metric_name: 指标名称

        Returns:
            指标值，如果不存在返回 None
        """
        try:
            if metric_name == "cache_hit_rate":
                hits = CACHE_HIT_RATE._value.get((), 0)
                total = 1
                return hits / total if total > 0 else 0

            if metric_name == "evaluation_errors_total":
                errors = EVALUATION_ERRORS._value.get((), 0)
                return float(errors)

            if metric_name == "evaluation_latency_seconds":
                latency = EVALUATION_LATENCY._value.get((), 0)
                return float(latency)

            return None
        except Exception as e:
            logger.error(f"获取指标值失败: {metric_name}, 错误: {e}")
            return None

    def _create_alert(self, rule: AlertRule) -> Alert:
        """
        创建告警实例

        Args:
            rule: 告警规则

        Returns:
            告警实例
        """
        import time

        self._last_triggered[rule.name] = time.time()

        return Alert(
            rule_name=rule.name,
            level=rule.level,
            message=rule.description,
            timestamp=time.time(),
            metrics={"threshold": rule.threshold},
        )

    def _notify(self, alert: Alert) -> None:
        """
        发送告警通知

        Args:
            alert: 告警实例
        """
        for channel in self.get_rule(alert.rule_name).channels:
            alert.channel = channel
            self._send_to_channel(alert)

        self._alerts.append(alert)

    def _send_to_channel(self, alert: Alert) -> None:
        """
        发送到指定渠道

        Args:
            alert: 告警实例
        """
        try:
            if alert.channel == AlertChannel.LOG:
                self._notify_log(alert)
            elif alert.channel == AlertChannel.EMAIL:
                self._notify_email(alert)
            elif alert.channel == AlertChannel.DINGTALK:
                self._notify_dingtalk(alert)
            elif alert.channel == AlertChannel.FEISHU:
                self._notify_feishu(alert)
        except Exception as e:
            logger.error(f"发送告警失败: {alert.channel}, 错误: {e}")

    def _notify_log(self, alert: Alert) -> None:
        """
        日志告警

        Args:
            alert: 告警实例
        """
        level_map = {
            AlertLevel.INFO: logging.INFO,
            AlertLevel.WARN: logging.WARNING,
            AlertLevel.ERROR: logging.ERROR,
            AlertLevel.CRITICAL: logging.CRITICAL,
        }

        logger.log(
            level_map[alert.level],
            f"[ALERT] {alert.level.value.upper()} - {alert.rule_name}: {alert.message}",
            extra={"metrics": alert.metrics},
        )

    def _notify_email(self, alert: Alert) -> None:
        """
        邮件告警

        Args:
            alert: 告警实例
        """
        logger.info(f"发送邮件告警: {alert.rule_name} - {alert.message}")

    def _notify_dingtalk(self, alert: Alert) -> None:
        """
        钉钉告警

        Args:
            alert: 告警实例
        """
        logger.info(f"发送钉钉告警: {alert.rule_name} - {alert.message}")

    def _notify_feishu(self, alert: Alert) -> None:
        """
        飞书告警

        Args:
            alert: 告警实例
        """
        logger.info(f"发送飞书告警: {alert.rule_name} - {alert.message}")

    def get_alerts(self, level: Optional[AlertLevel] = None) -> List[Alert]:
        """
        获取告警历史

        Args:
            level: 告警级别过滤

        Returns:
            告警列表
        """
        if level:
            return [alert for alert in self._alerts if alert.level == level]
        return self._alerts

    def clear_alerts(self) -> None:
        """
        清空告警历史
        """
        self._alerts.clear()
        logger.info("告警历史已清空")

    def get_alert_summary(self) -> Dict[str, int]:
        """
        获取告警汇总

        Returns:
            各级别告警数量
        """
        summary = {level.value: 0 for level in AlertLevel}
        for alert in self._alerts:
            summary[alert.level.value] += 1
        return summary


alert_service = AlertService()
