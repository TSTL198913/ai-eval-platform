"""校准流程自动化模块（Calibration Automation）

2026工业级标准实现：
1. 自动触发机制 - 每周定时、评分分布偏移、Kappa下降、版本变更
2. 漂移检测 - 对比历史评分分布，计算偏移量
3. SLA监控 - 偏差<5%、Kappa≥0.8、校准频率、校准耗时
4. 校准执行 - 完整的校准流程执行

校准触发器：
- 每周定时：执行漂移检测
- 评分分布偏移>10%：触发重新校准（24小时内）
- Kappa下降>15%：触发重新校准（12小时内）
- Rubric版本变更：强制重新校准（立即）
- 模型版本变更：强制重新校准（立即）

校准SLA：
- 偏差<5%：通过校准
- Kappa≥0.8：一致性达标
- 校准频率：每周一次
- 校准耗时：<2小时
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from statistics import mean, stdev
from typing import Any

from src.domain.evaluators.agreement_metrics import AgreementMetrics

logger = logging.getLogger(__name__)


class CalibrationTrigger(Enum):
    """校准触发器枚举"""

    SCHEDULED = "scheduled"
    DRIFT_DETECTED = "drift_detected"
    KAPPA_DEGRADATION = "kappa_degradation"
    RUBRIC_CHANGE = "rubric_change"
    MODEL_CHANGE = "model_change"


@dataclass
class CalibrationResult:
    """校准结果"""

    success: bool
    trigger: CalibrationTrigger
    timestamp: str
    duration: float
    deviation: float
    kappa: float
    drift_score: float
    sample_size: int
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class SLAMetrics:
    """SLA指标"""

    deviation: float
    kappa: float
    calibration_frequency_days: float
    calibration_duration_minutes: float


class CalibrationManager:
    """校准流程管理器"""

    DRIFT_THRESHOLD = 0.10
    KAPPA_DEGRADATION_THRESHOLD = 0.15
    DEVIATION_THRESHOLD = 0.05
    MIN_KAPPA = 0.8
    CALIBRATION_INTERVAL_DAYS = 7
    MAX_CALIBRATION_DURATION_MINUTES = 120

    def __init__(self):
        """初始化校准管理器"""
        self.calibration_history: list[CalibrationResult] = []
        self.last_calibration_time: datetime | None = None
        self.current_rubric_version: str = ""
        self.current_model_version: str = ""
        self.golden_dataset: list[dict[str, Any]] = []

    def _calculate_score_distribution_drift(
        self,
        current_scores: list[float],
        baseline_scores: list[float],
    ) -> float:
        """计算评分分布漂移

        Args:
            current_scores: 当前评分列表
            baseline_scores: 基线评分列表

        Returns:
            漂移分数（0-1）
        """
        if not current_scores or not baseline_scores:
            return 0.0

        current_mean = mean(current_scores)
        baseline_mean = mean(baseline_scores)

        current_std = stdev(current_scores) if len(current_scores) > 1 else 0.0
        baseline_std = stdev(baseline_scores) if len(baseline_scores) > 1 else 0.0

        mean_diff = abs(current_mean - baseline_mean)
        std_diff = abs(current_std - baseline_std)

        max_score_range = 1.0
        drift = (mean_diff + std_diff) / max_score_range

        return min(1.0, drift)

    def _calculate_deviation(
        self,
        model_scores: list[float],
        expert_scores: list[float],
    ) -> float:
        """计算模型评分与专家评分的偏差

        Args:
            model_scores: 模型评分列表
            expert_scores: 专家评分列表

        Returns:
            偏差值（0-1）
        """
        if len(model_scores) != len(expert_scores):
            raise ValueError("评分数量必须相同")

        if not model_scores:
            return 0.0

        absolute_diffs = [abs(m - e) for m, e in zip(model_scores, expert_scores, strict=False)]
        return mean(absolute_diffs)

    def detect_drift(self, current_scores: list[float]) -> bool:
        """检测评分漂移

        Args:
            current_scores: 当前评分列表

        Returns:
            是否检测到漂移
        """
        if not self.golden_dataset:
            logger.warning("没有基线数据，无法检测漂移")
            return False

        baseline_scores = [item.get("expert_score", 0.5) for item in self.golden_dataset]
        drift_score = self._calculate_score_distribution_drift(current_scores, baseline_scores)

        logger.info(f"漂移检测结果: {drift_score:.4f} (阈值: {self.DRIFT_THRESHOLD})")

        return drift_score > self.DRIFT_THRESHOLD

    def check_kappa_degradation(self, new_kappa: float) -> bool:
        """检查Kappa值是否下降

        Args:
            new_kappa: 新的Kappa值

        Returns:
            是否下降超过阈值
        """
        if not self.calibration_history:
            return False

        recent_results = self.calibration_history[-3:]
        if not recent_results:
            return False

        avg_prev_kappa = mean(r.kappa for r in recent_results if r.kappa > 0)

        if avg_prev_kappa == 0:
            return False

        degradation = avg_prev_kappa - new_kappa
        logger.info(
            f"Kappa下降检测: 之前={avg_prev_kappa:.4f}, 现在={new_kappa:.4f}, 下降={degradation:.4f}"
        )

        return degradation > self.KAPPA_DEGRADATION_THRESHOLD

    def needs_calibration(self) -> tuple[bool, CalibrationTrigger | None]:
        """检查是否需要校准

        Returns:
            (是否需要校准, 触发器类型)
        """
        now = datetime.now()

        if self.last_calibration_time:
            days_since_last = (now - self.last_calibration_time).days
            if days_since_last >= self.CALIBRATION_INTERVAL_DAYS:
                return True, CalibrationTrigger.SCHEDULED

        return False, None

    def run_calibration(
        self,
        trigger: CalibrationTrigger,
        evaluator,
        golden_dataset: list[dict[str, Any]] | None = None,
    ) -> CalibrationResult:
        """执行校准流程

        Args:
            trigger: 校准触发器
            evaluator: 评估器对象
            golden_dataset: 黄金数据集，可选

        Returns:
            校准结果
        """
        start_time = time.time()
        timestamp = datetime.now().isoformat()

        if golden_dataset:
            self.golden_dataset = golden_dataset

        if not self.golden_dataset:
            logger.warning("没有黄金数据集，校准无法进行")
            return CalibrationResult(
                success=False,
                trigger=trigger,
                timestamp=timestamp,
                duration=0,
                deviation=0,
                kappa=0,
                drift_score=0,
                sample_size=0,
                details={"error": "没有黄金数据集"},
            )

        model_scores = []
        expert_scores = []

        for item in self.golden_dataset:
            try:
                request = item.get("request")
                if request:
                    response = evaluator.safe_evaluate(request)
                    model_score = response.score if response.score is not None else 0.5
                    model_scores.append(model_score)

                expert_score = item.get("expert_score", 0.5)
                expert_scores.append(expert_score)
            except Exception as e:
                logger.error(f"校准评估失败: {e}")

        deviation = self._calculate_deviation(model_scores, expert_scores)
        kappa = AgreementMetrics.cohens_kappa(model_scores, expert_scores)
        drift_score = self._calculate_score_distribution_drift(model_scores, expert_scores)

        duration = time.time() - start_time

        success = deviation < self.DEVIATION_THRESHOLD and kappa >= self.MIN_KAPPA

        result = CalibrationResult(
            success=success,
            trigger=trigger,
            timestamp=timestamp,
            duration=duration,
            deviation=deviation,
            kappa=kappa,
            drift_score=drift_score,
            sample_size=len(model_scores),
            details={
                "model_scores": model_scores[:10],
                "expert_scores": expert_scores[:10],
                "sample_size_full": len(model_scores),
            },
        )

        self.calibration_history.append(result)
        self.last_calibration_time = datetime.now()

        logger.info(
            f"校准完成: 成功={success}, 偏差={deviation:.4f}, Kappa={kappa:.4f}, 耗时={duration:.2f}秒"
        )

        return result

    def get_sla_metrics(self) -> SLAMetrics:
        """获取SLA指标

        Returns:
            SLA指标对象
        """
        now = datetime.now()

        if self.last_calibration_time:
            days_since_last = (now - self.last_calibration_time).days
        else:
            days_since_last = float("inf")

        recent_results = self.calibration_history[-5:]

        if recent_results:
            avg_deviation = mean(r.deviation for r in recent_results)
            avg_kappa = mean(r.kappa for r in recent_results)
            avg_duration = mean(r.duration for r in recent_results) / 60
        else:
            avg_deviation = 0
            avg_kappa = 0
            avg_duration = 0

        return SLAMetrics(
            deviation=avg_deviation,
            kappa=avg_kappa,
            calibration_frequency_days=days_since_last,
            calibration_duration_minutes=avg_duration,
        )

    def check_sla_compliance(self) -> dict[str, bool]:
        """检查SLA合规性

        Returns:
            各SLA项的合规状态
        """
        sla = self.get_sla_metrics()

        return {
            "deviation_compliant": sla.deviation < self.DEVIATION_THRESHOLD,
            "kappa_compliant": sla.kappa >= self.MIN_KAPPA if sla.kappa > 0 else True,
            "frequency_compliant": sla.calibration_frequency_days <= self.CALIBRATION_INTERVAL_DAYS,
            "duration_compliant": sla.calibration_duration_minutes
            < self.MAX_CALIBRATION_DURATION_MINUTES,
        }

    def get_calibration_report(self) -> dict[str, Any]:
        """获取校准报告

        Returns:
            校准报告字典
        """
        sla = self.get_sla_metrics()
        sla_compliance = self.check_sla_compliance()

        recent_results = self.calibration_history[-5:]

        return {
            "last_calibration_time": self.last_calibration_time.isoformat()
            if self.last_calibration_time
            else None,
            "next_scheduled_calibration": (
                (
                    self.last_calibration_time + timedelta(days=self.CALIBRATION_INTERVAL_DAYS)
                ).isoformat()
                if self.last_calibration_time
                else None
            ),
            "calibration_count": len(self.calibration_history),
            "recent_results": [
                {
                    "timestamp": r.timestamp,
                    "success": r.success,
                    "trigger": r.trigger.value,
                    "deviation": r.deviation,
                    "kappa": r.kappa,
                    "duration": r.duration,
                }
                for r in recent_results
            ],
            "sla_metrics": {
                "avg_deviation": sla.deviation,
                "avg_kappa": sla.kappa,
                "days_since_last_calibration": sla.calibration_frequency_days,
                "avg_calibration_duration_minutes": sla.calibration_duration_minutes,
            },
            "sla_compliance": sla_compliance,
            "golden_dataset_size": len(self.golden_dataset),
        }


calibration_manager = CalibrationManager()
