"""
自适应校准器 (AdaptiveCalibrator)
监控评估器偏差并在偏差超过阈值时触发警报和自动校准

核心功能：
- 实时监控评估器输出与期望值的偏差
- 当偏差超过 5% 时触发警报
- 支持自动校准和手动校准模式
- 提供校准报告和趋势分析
"""

import json
import logging
import threading
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from src.config import settings
from src.schemas.evaluation import DomainResponse, EvaluationSchema

logger = logging.getLogger(__name__)


class CalibrationAlert:
    """校准警报"""
    
    def __init__(
        self,
        evaluator_type: str,
        deviation: float,
        threshold: float,
        severity: str,
        message: str,
        timestamp: float = None,
    ):
        self.evaluator_type = evaluator_type
        self.deviation = deviation
        self.threshold = threshold
        self.severity = severity
        self.message = message
        self.timestamp = timestamp or time.time()
        self.resolved = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evaluator_type": self.evaluator_type,
            "deviation": round(self.deviation, 4),
            "threshold": self.threshold,
            "severity": self.severity,
            "message": self.message,
            "timestamp": self.timestamp,
            "resolved": self.resolved,
        }


class CalibrationStats:
    """校准统计信息"""
    
    def __init__(self):
        self.scores: List[float] = []
        self.expected_scores: List[float] = []
        self.confidences: List[float] = []
        self.count = 0
        self.mean_deviation = 0.0
        self.std_deviation = 0.0
        self.max_deviation = 0.0
        self.min_deviation = 0.0
        self.confidence_mean = 0.0
        self.last_updated = 0.0

    def update(self, score: float, expected_score: float, confidence: float):
        self.scores.append(score)
        self.expected_scores.append(expected_score)
        self.confidences.append(confidence)
        self.count += 1
        self.last_updated = time.time()
        self._calculate_stats()

    def _calculate_stats(self):
        self.confidence_mean = float(np.mean(self.confidences)) if self.confidences else 0.0
        
        if self.count < 2:
            return
        
        score_array = np.array(self.scores)
        expected_array = np.array(self.expected_scores)
        deviations = np.abs(score_array - expected_array)
        
        self.mean_deviation = float(np.mean(deviations))
        self.std_deviation = float(np.std(deviations))
        self.max_deviation = float(np.max(deviations))
        self.min_deviation = float(np.min(deviations))

    def get_alert(self, threshold: float = 0.05) -> Optional[CalibrationAlert]:
        if self.count < 5:
            return None
        
        if self.mean_deviation > threshold + 1e-9:
            severity = self._determine_severity(self.mean_deviation, threshold)
            return CalibrationAlert(
                evaluator_type="unknown",
                deviation=self.mean_deviation,
                threshold=threshold,
                severity=severity,
                message=f"评估器偏差超过阈值: {self.mean_deviation:.4f} > {threshold}",
            )
        return None

    def _determine_severity(self, deviation: float, threshold: float) -> str:
        ratio = deviation / threshold
        if ratio >= 2.0:
            return "critical"
        elif ratio >= 1.5:
            return "high"
        elif ratio >= 1.2:
            return "medium"
        else:
            return "low"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "count": self.count,
            "mean_deviation": round(self.mean_deviation, 4),
            "std_deviation": round(self.std_deviation, 4),
            "max_deviation": round(self.max_deviation, 4),
            "min_deviation": round(self.min_deviation, 4),
            "last_updated": self.last_updated,
            "confidence_mean": round(np.mean(self.confidences), 4) if self.confidences else 0.0,
        }


class AdaptiveCalibrator:
    """
    自适应校准器
    
    监控评估器输出与期望值的偏差，当偏差超过阈值时触发警报。
    
    工作流程：
    1. 收集评估结果和期望分数
    2. 计算偏差统计（均值、标准差、最大/最小偏差）
    3. 当偏差超过阈值时触发警报
    4. 支持自动校准和手动校准
    """

    _instance = None
    _lock = threading.RLock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        self._evaluator_stats: Dict[str, CalibrationStats] = defaultdict(CalibrationStats)
        self._alerts: List[CalibrationAlert] = []
        self._lock = threading.RLock()
        self._threshold = getattr(settings, 'calibration_threshold', 0.05)
        self._min_sample_size = getattr(settings, 'calibration_min_samples', 5)
        self._calibration_cache: Dict[str, Tuple[float, float]] = {}
        self._initialized = True
        logger.info("AdaptiveCalibrator 初始化完成")

    def record_evaluation(
        self,
        evaluator_type: str,
        result: DomainResponse,
        expected_score: float,
    ):
        """记录评估结果用于校准"""
        if result.score is None:
            return
        
        with self._lock:
            stats = self._evaluator_stats[evaluator_type]
            confidence = result.confidence if result.confidence is not None else 0.0
            stats.update(result.score, expected_score, confidence)

            alert = stats.get_alert(self._threshold)
            if alert:
                alert.evaluator_type = evaluator_type
                self._alerts.append(alert)
                logger.warning(
                    f"校准警报 | evaluator={evaluator_type} | deviation={stats.mean_deviation:.4f} | "
                    f"severity={alert.severity} | message={alert.message}"
                )

    def check_deviation(self, evaluator_type: str) -> Optional[CalibrationAlert]:
        """检查评估器偏差"""
        with self._lock:
            stats = self._evaluator_stats.get(evaluator_type)
            if stats is None or stats.count < self._min_sample_size:
                return None
            
            return stats.get_alert(self._threshold)

    def get_all_alerts(self, resolved: bool = False) -> List[CalibrationAlert]:
        """获取所有警报"""
        with self._lock:
            if resolved:
                return [a for a in self._alerts if a.resolved]
            return [a for a in self._alerts if not a.resolved]

    def resolve_alert(self, alert_index: int) -> bool:
        """解决警报"""
        with self._lock:
            if 0 <= alert_index < len(self._alerts):
                self._alerts[alert_index].resolved = True
                return True
            return False

    def get_evaluator_stats(self, evaluator_type: str) -> Optional[CalibrationStats]:
        """获取评估器统计信息"""
        with self._lock:
            return self._evaluator_stats.get(evaluator_type)

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取所有评估器统计信息"""
        with self._lock:
            return {
                evaluator: stats.to_dict()
                for evaluator, stats in self._evaluator_stats.items()
            }

    def calibrate(self, evaluator_type: str) -> bool:
        """执行自动校准"""
        with self._lock:
            stats = self._evaluator_stats.get(evaluator_type)
            if stats is None or stats.count < self._min_sample_size:
                logger.warning(f"样本不足，无法校准: {evaluator_type}")
                return False

            if stats.mean_deviation <= self._threshold:
                logger.info(f"评估器已校准: {evaluator_type}, 偏差={stats.mean_deviation:.4f}")
                return True

            calibration_factor = self._calculate_calibration_factor(stats)
            self._calibration_cache[evaluator_type] = (calibration_factor, time.time())
            
            logger.info(
                f"自动校准完成 | evaluator={evaluator_type} | "
                f"factor={calibration_factor:.4f} | deviation={stats.mean_deviation:.4f}"
            )
            
            return True

    def _calculate_calibration_factor(self, stats: CalibrationStats) -> float:
        """计算校准因子"""
        if stats.count == 0:
            return 1.0
        
        score_array = np.array(stats.scores)
        expected_array = np.array(stats.expected_scores)
        
        valid_mask = expected_array != 0
        if np.sum(valid_mask) == 0:
            return 1.0
        
        ratios = score_array[valid_mask] / expected_array[valid_mask]
        return float(np.mean(ratios))

    def apply_calibration(self, evaluator_type: str, score: float) -> float:
        """应用校准因子"""
        with self._lock:
            if evaluator_type in self._calibration_cache:
                factor, timestamp = self._calibration_cache[evaluator_type]
                calibrated = score * factor
                return max(0.0, min(1.0, calibrated))
        return score

    def get_calibration_report(self) -> str:
        """生成校准报告"""
        with self._lock:
            lines = [
                "=" * 70,
                "自适应校准报告",
                "=" * 70,
                f"阈值: {self._threshold * 100:.1f}%",
                f"最小样本数: {self._min_sample_size}",
                "",
            ]

            lines.append("评估器统计:")
            for evaluator, stats in self._evaluator_stats.items():
                if stats.count == 0:
                    continue
                status = "✓ 正常" if stats.mean_deviation <= self._threshold else "✗ 偏差"
                lines.append(
                    f"  {evaluator}: "
                    f"样本={stats.count}, "
                    f"平均偏差={stats.mean_deviation:.4f}, "
                    f"置信度={stats.confidence_mean:.4f}, "
                    f"{status}"
                )

            unresolved = [a for a in self._alerts if not a.resolved]
            if unresolved:
                lines.append("\n未解决警报:")
                for i, alert in enumerate(unresolved):
                    lines.append(
                        f"  [{i}] {alert.severity.upper()} | "
                        f"{alert.evaluator_type} | "
                        f"偏差={alert.deviation:.4f}"
                    )
            else:
                lines.append("\n未解决警报: 无")

            lines.append("\n" + "=" * 70)
            
            return "\n".join(lines)

    def reset(self):
        """重置校准器状态"""
        with self._lock:
            self._evaluator_stats.clear()
            self._alerts.clear()
            self._calibration_cache.clear()
            logger.info("AdaptiveCalibrator 已重置")

    @classmethod
    def get_instance(cls) -> "AdaptiveCalibrator":
        """获取单例实例"""
        return cls()


calibrator = AdaptiveCalibrator()