"""
自适应校准器 (AdaptiveCalibrator)
监控评估器偏差并在偏差超过阈值时触发警报和自动校准

核心功能：
- 实时监控评估器输出与期望值的偏差
- 当偏差超过 5% 时触发警报
- 支持自动校准和手动校准模式
- 提供校准报告和趋势分析
- 黄金数据集校准（2026工业级标准）
- 执行前校准检查（pre_execution_check）
"""

import json
import logging
import os
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from enum import Enum
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

import numpy as np

from src.config import settings
from src.domain.statistical_analysis import statistical_analyzer
from src.infra.cache import redis_cluster_manager
from src.schemas.evaluation import DomainResponse

logger = logging.getLogger(__name__)


class CalibrationStatus(Enum):
    NOT_CALIBRATED = "not_calibrated"
    NO_VERSION = "no_version"
    CALIBRATING = "calibrating"
    CALIBRATED = "calibrated"
    DRIFTED = "drifted"
    REJECTED = "rejected"


@dataclass
class CalibrationResult:
    evaluator_name: str
    evaluator_version: str
    dataset_name: str
    dataset_id: str

    n_samples: int
    gold_scores: list[float]
    eval_scores: list[float]

    mean_gold: float
    mean_eval: float
    mean_deviation: float
    max_deviation: float
    rmse: float

    correlation: float
    is_calibrated: bool
    deviation_threshold: float
    confidence_interval: tuple[float, float]

    suggestions: list[str]

    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluator_name": self.evaluator_name,
            "evaluator_version": self.evaluator_version,
            "dataset_name": self.dataset_name,
            "dataset_id": self.dataset_id,
            "n_samples": self.n_samples,
            "mean_gold": round(self.mean_gold, 2),
            "mean_eval": round(self.mean_eval, 2),
            "mean_deviation": round(self.mean_deviation, 2),
            "max_deviation": round(self.max_deviation, 2),
            "rmse": round(self.rmse, 4),
            "correlation": round(self.correlation, 4),
            "is_calibrated": self.is_calibrated,
            "deviation_threshold": self.deviation_threshold,
            "confidence_interval": [round(x, 2) for x in self.confidence_interval],
            "suggestions": self.suggestions,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class PreExecutionCheck:
    evaluator_name: str
    evaluator_version: str | None
    can_proceed: bool
    status: CalibrationStatus

    calibration_result: CalibrationResult | None = None
    message: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        result = {
            "evaluator_name": self.evaluator_name,
            "evaluator_version": self.evaluator_version,
            "can_proceed": self.can_proceed,
            "status": self.status.value,
            "message": self.message,
            "warnings": self.warnings,
        }
        if self.calibration_result:
            result["calibration_result"] = self.calibration_result.to_dict()
        return result


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

    @classmethod
    def _reset_instance(cls):
        """重置单例实例（仅用于测试）"""
        with cls._lock:
            cls._instance = None

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, default_threshold: float = None, min_calibration_samples: int = None, calibration_interval: int = None):
        if self._initialized:
            if default_threshold is not None:
                self._default_threshold = default_threshold
            if min_calibration_samples is not None:
                self._min_calibration_samples = min_calibration_samples
            if calibration_interval is not None:
                self._calibration_interval = calibration_interval
            return
        
        self._evaluator_stats: Dict[str, CalibrationStats] = defaultdict(CalibrationStats)
        self._alerts: List[CalibrationAlert] = []
        self._lock = threading.RLock()
        self._threshold = getattr(settings, 'calibration_threshold', 0.05)
        self._min_sample_size = getattr(settings, 'calibration_min_samples', 5)
        self._calibration_cache: Dict[str, Tuple[float, float]] = {}
        self._golden_calibration_cache: dict[str, dict[str, Any]] = {}
        self._calibration_interval = calibration_interval or 24
        
        self._default_threshold = default_threshold or 5.0
        self._min_calibration_samples = min_calibration_samples or 5

        self._redis_client = None
        try:
            self._redis_client = redis_cluster_manager.get_client()
            if self._redis_client:
                logger.info("AdaptiveCalibrator Redis客户端连接成功")
            else:
                logger.warning("AdaptiveCalibrator Redis客户端获取失败，将使用本地文件缓存")
        except Exception as e:
            logger.warning(f"AdaptiveCalibrator Redis客户端连接失败: {e}，将使用本地文件缓存")
        
        self._load_state_from_redis()
        self._load_golden_calibration_cache()
        self._initialized = True
        logger.info("AdaptiveCalibrator 初始化完成")

    def _load_golden_calibration_cache(self):
        cache_file = "data/calibration_cache.json"
        if os.path.exists(cache_file):
            try:
                with open(cache_file, encoding="utf-8") as f:
                    self._golden_calibration_cache = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load golden calibration cache: {e}")

    def _save_golden_calibration_cache(self):
        cache_file = "data/calibration_cache.json"
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(self._golden_calibration_cache, f, ensure_ascii=False, indent=2)

    def _get_golden_cache_key(self, evaluator_name: str, dataset_id: str) -> str:
        return f"{evaluator_name}:{dataset_id}"

    def _is_golden_cache_valid(self, evaluator_name: str, dataset_id: str) -> bool:
        key = self._get_golden_cache_key(evaluator_name, dataset_id)
        if key not in self._golden_calibration_cache:
            return False

        cached = self._golden_calibration_cache[key]
        cached_time = datetime.fromisoformat(cached["timestamp"])
        hours_elapsed = (datetime.utcnow() - cached_time).total_seconds() / 3600

        return hours_elapsed < self._calibration_interval

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
        
        self._save_state_to_redis()

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
        
        self._save_state_to_redis()
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

    def run_golden_calibration(
        self,
        evaluator_name: str,
        evaluator_func: callable,
        dataset_id: str,
        threshold: float = None,
    ) -> CalibrationResult:
        """在黄金数据集上运行校准

        Args:
            evaluator_name: 评估器名称
            evaluator_func: 评估函数 (接收一个样本，返回分数)
            dataset_id: 黄金数据集ID
            threshold: 偏差阈值 (默认使用系统配置)
        """
        from src.domain.adaptive_calibration import golden_dataset_manager
        dataset = golden_dataset_manager.get_dataset(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset '{dataset_id}' not found")

        samples = [s for s in dataset.samples if s.scores]
        if len(samples) < self._min_sample_size:
            raise ValueError(f"至少需要 {self._min_sample_size} 个带标注的样本")

        threshold = threshold or self._threshold

        from src.domain.adaptive_calibration import evaluator_version_manager
        version_info = evaluator_version_manager.get_current_version(evaluator_name)
        evaluator_version = version_info.version if version_info else "unknown"

        gold_scores = []
        eval_scores = []
        suggestions = []
        failed_samples = 0

        for sample in samples:
            gold_score = sum(sample.scores.values()) / len(sample.scores)

            try:
                eval_result = evaluator_func(sample)
                eval_score = eval_result.get("score", eval_result.get("total_score", None))
                if eval_score is None:
                    raise ValueError("评估结果缺少 score 字段")
                gold_scores.append(gold_score)
                eval_scores.append(eval_score)
            except Exception as e:
                failed_samples += 1
                suggestions.append(f"样本 {sample.id} 评估失败: {str(e)}")

        n_effective = len(gold_scores)

        if n_effective < self._min_sample_size:
            suggestions.append(
                f"有效样本不足: 共{len(samples)}个样本，成功评估{n_effective}个，"
                f"失败{failed_samples}个，至少需要{self._min_sample_size}个有效样本"
            )
            return CalibrationResult(
                evaluator_name=evaluator_name,
                evaluator_version=evaluator_version,
                dataset_name=dataset.name,
                dataset_id=dataset_id,
                n_samples=0,
                gold_scores=[],
                eval_scores=[],
                mean_gold=0.0,
                mean_eval=0.0,
                mean_deviation=0.0,
                max_deviation=0.0,
                rmse=0.0,
                correlation=0.0,
                is_calibrated=False,
                deviation_threshold=threshold,
                confidence_interval=(0.0, 0.0),
                suggestions=suggestions,
            )

        mean_gold = sum(gold_scores) / len(gold_scores)
        mean_eval = sum(eval_scores) / len(eval_scores)
        mean_deviation = abs(mean_eval - mean_gold)
        max_deviation = max(abs(e - g) for e, g in zip(eval_scores, gold_scores, strict=False))

        rmse = np.sqrt(
            sum((e - g) ** 2 for e, g in zip(eval_scores, gold_scores, strict=False))
            / len(eval_scores)
        )

        if len(gold_scores) > 1:
            correlation = float(np.corrcoef(gold_scores, eval_scores)[0, 1])
            if np.isnan(correlation):
                correlation = 0.0
        else:
            correlation = 1.0

        deviations = [abs(e - g) for e, g in zip(eval_scores, gold_scores, strict=True)]
        ci_result = statistical_analyzer.calculate_confidence_interval(deviations, confidence=0.95)
        confidence_interval = (ci_result.lower, ci_result.upper)

        is_calibrated = mean_deviation <= threshold

        if mean_deviation > threshold:
            suggestions.append(f"评估器偏差 {mean_deviation:.2f} 超过阈值 {threshold}")
        if max_deviation > threshold * 2:
            suggestions.append(f"存在极端偏差样本 (最大偏差 {max_deviation:.2f})")
        if correlation < 0.7:
            suggestions.append(f"与专家评分相关性偏低 ({correlation:.2f})，建议检查评估逻辑")
        if failed_samples > 0:
            suggestions.append(f"有 {failed_samples} 个样本评估失败，仅基于 {n_effective} 个有效样本计算")

        if is_calibrated:
            suggestions.append("校准通过，评估器可正常使用")

        result = CalibrationResult(
            evaluator_name=evaluator_name,
            evaluator_version=evaluator_version,
            dataset_name=dataset.name,
            dataset_id=dataset_id,
            n_samples=n_effective,
            gold_scores=gold_scores,
            eval_scores=eval_scores,
            mean_gold=mean_gold,
            mean_eval=mean_eval,
            mean_deviation=mean_deviation,
            max_deviation=max_deviation,
            rmse=rmse,
            correlation=correlation,
            is_calibrated=is_calibrated,
            deviation_threshold=threshold,
            confidence_interval=confidence_interval,
            suggestions=suggestions,
        )

        key = self._get_golden_cache_key(evaluator_name, dataset_id)
        self._golden_calibration_cache[key] = {
            "is_calibrated": is_calibrated,
            "mean_deviation": mean_deviation,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._save_golden_calibration_cache()

        from src.domain.adaptive_calibration import evaluator_version_manager
        evaluator_version_manager.update_calibration(evaluator_name, mean_eval)

        return result

    def run_calibration(
        self,
        evaluator_name: str,
        evaluator_func: callable,
        dataset_id: str,
        threshold: float = None,
    ) -> CalibrationResult:
        return self.run_golden_calibration(evaluator_name, evaluator_func, dataset_id, threshold)

    def _get_cache_key(self, evaluator_name: str, dataset_id: str) -> str:
        return f"{evaluator_name}:{dataset_id}"

    def _is_cache_valid(self, evaluator_name: str, dataset_id: str) -> bool:
        key = self._get_cache_key(evaluator_name, dataset_id)
        if key not in self._calibration_cache:
            return False

        cached = self._calibration_cache[key]
        if isinstance(cached, dict):
            timestamp_str = cached.get("timestamp")
            if timestamp_str:
                try:
                    cached_time = datetime.fromisoformat(timestamp_str)
                    hours_elapsed = (datetime.utcnow() - cached_time).total_seconds() / 3600
                    interval = getattr(self, '_calibration_interval', 24)
                    return hours_elapsed < interval
                except (ValueError, TypeError):
                    return False
        elif isinstance(cached, tuple):
            _, timestamp = cached
            hours_elapsed = (time.time() - timestamp) / 3600
            interval = getattr(self, '_calibration_interval', 24)
            return hours_elapsed < interval
        return False

    def _generate_recommendations(self, evaluator_name: str) -> list[str]:
        recommendations = []
        from src.domain.adaptive_calibration import evaluator_version_manager
        status_info = evaluator_version_manager.check_calibration_status(evaluator_name)
        status = status_info.get("status", "")
        
        if status == "drifted":
            recommendations.append("评估器已漂移，建议立即重新校准")
            recommendations.append("检查评估器逻辑是否有变化")
            recommendations.append("考虑在黄金数据集上重新训练")
        elif status == "not_calibrated":
            recommendations.append("评估器尚未校准，建议先在黄金数据集上校准")
            recommendations.append("注册评估器版本以启用校准追踪")
        
        return recommendations

    def pre_execution_check(self, evaluator_name: str, dataset_id: str = None) -> PreExecutionCheck:
        """执行前检查

        Returns:
            PreExecutionCheck: 检查结果，决定是否允许执行评估
        """
        from src.domain.adaptive_calibration import evaluator_version_manager
        version_info = evaluator_version_manager.get_current_version(evaluator_name)
        if not version_info:
            return PreExecutionCheck(
                evaluator_name=evaluator_name,
                evaluator_version=None,
                can_proceed=True,
                status=CalibrationStatus.NO_VERSION,
                message="评估器未注册版本，建议先注册版本",
                warnings=["评估结果可能不可靠", "建议先在黄金数据集上校准"],
            )
        else:
            evaluator_version = version_info.version

        if dataset_id:
            if not self._is_cache_valid(evaluator_name, dataset_id):
                return PreExecutionCheck(
                    evaluator_name=evaluator_name,
                    evaluator_version=evaluator_version,
                    can_proceed=False,
                    status=CalibrationStatus.NOT_CALIBRATED,
                    message=f"评估器尚未在数据集 {dataset_id} 上校准，或校准已过期",
                )

            key = self._get_cache_key(evaluator_name, dataset_id)
            cached = self._calibration_cache.get(key, {})
            is_calibrated = cached.get("is_calibrated", False)

            if is_calibrated:
                return PreExecutionCheck(
                    evaluator_name=evaluator_name,
                    evaluator_version=evaluator_version,
                    can_proceed=True,
                    status=CalibrationStatus.CALIBRATED,
                    message="校准检查通过",
                )
            else:
                mean_deviation = cached.get("mean_deviation", 0)
                return PreExecutionCheck(
                    evaluator_name=evaluator_name,
                    evaluator_version=evaluator_version,
                    can_proceed=False,
                    status=CalibrationStatus.DRIFTED,
                    message=f"评估器偏差 {mean_deviation:.2f} 超过阈值，需要重新校准",
                    warnings=["评估器已偏离校准区间"],
                )

        from src.domain.adaptive_calibration import evaluator_version_manager
        calibration_status = evaluator_version_manager.check_calibration_status(evaluator_name)
        can_proceed = calibration_status.get("can_proceed", True)

        if not calibration_status.get("calibration_score"):
            return PreExecutionCheck(
                evaluator_name=evaluator_name,
                evaluator_version=evaluator_version,
                can_proceed=True,
                status=CalibrationStatus.NOT_CALIBRATED,
                message="评估器尚未校准，建议先在黄金数据集上校准",
                warnings=["评估结果可能不可靠"],
            )

        if not can_proceed:
            return PreExecutionCheck(
                evaluator_name=evaluator_name,
                evaluator_version=evaluator_version,
                can_proceed=False,
                status=CalibrationStatus.DRIFTED,
                message="评估器偏离校准区间，系统拒绝执行",
            )

        return PreExecutionCheck(
            evaluator_name=evaluator_name,
            evaluator_version=evaluator_version,
            can_proceed=True,
            status=CalibrationStatus.CALIBRATED,
            message="校准检查通过",
        )

    def get_golden_calibration_report(self, evaluator_name: str) -> dict[str, Any]:
        """获取黄金数据集校准报告"""
        from src.domain.adaptive_calibration import evaluator_version_manager
        version_info = evaluator_version_manager.get_current_version(evaluator_name)

        return {
            "evaluator_name": evaluator_name,
            "version": version_info.version if version_info else "unknown",
            "calibration_history": evaluator_version_manager.get_version_history(evaluator_name),
            "calibration_status": evaluator_version_manager.check_calibration_status(
                evaluator_name
            ),
            "cached_datasets": [
                {
                    "dataset_id": k.split(":")[1],
                    "is_calibrated": v.get("is_calibrated"),
                    "mean_deviation": v.get("mean_deviation"),
                    "timestamp": v.get("timestamp"),
                }
                for k, v in self._golden_calibration_cache.items()
                if k.startswith(f"{evaluator_name}:")
            ],
            "recommendations": self._generate_recommendations(evaluator_name),
        }

    def _generate_recommendations(self, evaluator_name: str) -> list[str]:
        recommendations = []
        from src.domain.adaptive_calibration import evaluator_version_manager
        status = evaluator_version_manager.check_calibration_status(evaluator_name)

        if status.get("status") == "drifted":
            recommendations.append("立即对评估器进行重新校准")
            recommendations.append("检查评估器最近的代码变更")
        elif status.get("status") == "not_calibrated":
            recommendations.append("建议使用黄金数据集对评估器进行首次校准")
        else:
            recommendations.append("评估器状态正常")

        from src.domain.adaptive_calibration import golden_dataset_manager
        datasets = golden_dataset_manager.list_datasets()
        if datasets:
            recommendations.append(f"可用的黄金数据集: {', '.join([d.name for d in datasets[:3]])}")

        return recommendations

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

        current_mean = float(np.mean(current_scores))
        baseline_mean = float(np.mean(baseline_scores))

        current_std = float(np.std(current_scores)) if len(current_scores) > 1 else 0.0
        baseline_std = float(np.std(baseline_scores)) if len(baseline_scores) > 1 else 0.0

        mean_diff = abs(current_mean - baseline_mean)
        std_diff = abs(current_std - baseline_std)

        max_score_range = 1.0
        drift = (mean_diff + std_diff) / max_score_range

        return min(1.0, drift)

    def detect_drift(self, evaluator_name: str, current_scores: list[float]) -> bool:
        """检测评分漂移

        Args:
            evaluator_name: 评估器名称
            current_scores: 当前评分列表

        Returns:
            是否检测到漂移
        """
        from src.domain.adaptive_calibration import golden_dataset_manager
        dataset = golden_dataset_manager.get_dataset_by_category(evaluator_name)
        if not dataset:
            logger.warning(f"评估器 {evaluator_name} 没有基线数据，无法检测漂移")
            return False

        baseline_scores = []
        for sample in dataset.samples:
            if sample.scores:
                baseline_scores.append(sum(sample.scores.values()) / len(sample.scores))

        if not baseline_scores:
            logger.warning(f"评估器 {evaluator_name} 没有带标注的基线样本")
            return False

        drift_score = self._calculate_score_distribution_drift(current_scores, baseline_scores)
        drift_threshold = 0.10

        logger.info(f"漂移检测结果 | evaluator={evaluator_name} | drift={drift_score:.4f} | threshold={drift_threshold}")

        return drift_score > drift_threshold

    def check_kappa_degradation(self, evaluator_name: str, new_kappa: float) -> bool:
        """检查Kappa值是否下降

        Args:
            evaluator_name: 评估器名称
            new_kappa: 新的Kappa值

        Returns:
            是否下降超过阈值
        """
        stats = self._evaluator_stats.get(evaluator_name)
        if not stats or stats.count < 3:
            return False

        recent_scores = stats.scores[-5:]
        recent_expected = stats.expected_scores[-5:]

        if len(recent_scores) < 2:
            return False

        from src.domain.evaluators.agreement_metrics import AgreementMetrics
        prev_kappa = AgreementMetrics.cohens_kappa(recent_scores, recent_expected)

        if prev_kappa <= 0:
            return False

        degradation = prev_kappa - new_kappa
        kappa_degradation_threshold = 0.15

        logger.info(
            f"Kappa下降检测 | evaluator={evaluator_name} | previous={prev_kappa:.4f} | "
            f"current={new_kappa:.4f} | degradation={degradation:.4f}"
        )

        return degradation > kappa_degradation_threshold

    def get_sla_metrics(self, evaluator_name: str) -> dict[str, Any]:
        """获取SLA指标"""
        stats = self._evaluator_stats.get(evaluator_name)
        now = datetime.utcnow()

        last_calibration_time = None
        for alert in reversed(self._alerts):
            if alert.evaluator_type == evaluator_name:
                last_calibration_time = datetime.fromtimestamp(alert.timestamp)
                break

        if last_calibration_time:
            days_since_last = (now - last_calibration_time).days
        else:
            days_since_last = float("inf")

        if stats and stats.count >= 5:
            avg_deviation = stats.mean_deviation
            scores = stats.scores[-5:]
            expected = stats.expected_scores[-5:]
            if len(scores) >= 2:
                from src.domain.evaluators.agreement_metrics import AgreementMetrics
                kappa = AgreementMetrics.cohens_kappa(scores, expected)
            else:
                kappa = 0.0
        else:
            avg_deviation = 0.0
            kappa = 0.0

        return {
            "deviation": avg_deviation,
            "kappa": kappa,
            "calibration_frequency_days": days_since_last,
        }

    def check_sla_compliance(self, evaluator_name: str) -> dict[str, bool]:
        """检查SLA合规性"""
        sla = self.get_sla_metrics(evaluator_name)
        deviation_threshold = 0.05
        min_kappa = 0.8
        calibration_interval_days = 7

        return {
            "deviation_compliant": sla["deviation"] < deviation_threshold,
            "kappa_compliant": sla["kappa"] >= min_kappa if sla["kappa"] > 0 else True,
            "frequency_compliant": sla["calibration_frequency_days"] <= calibration_interval_days,
        }

    def _save_state_to_redis(self):
        """保存校准状态到Redis"""
        if not self._redis_client:
            return
        
        try:
            with self._lock:
                state_data = {
                    "evaluator_stats": {
                        evaluator: stats.to_dict()
                        for evaluator, stats in self._evaluator_stats.items()
                    },
                    "calibration_cache": {
                        evaluator: {"factor": factor, "timestamp": timestamp}
                        for evaluator, (factor, timestamp) in self._calibration_cache.items()
                    },
                    "alerts": [alert.to_dict() for alert in self._alerts],
                }
                
                state_json = json.dumps(state_data, ensure_ascii=False)
                self._redis_client.setex("calibration:state", 86400, state_json)
                logger.debug("AdaptiveCalibrator状态已保存到Redis")
        except Exception as e:
            logger.error(f"AdaptiveCalibrator保存状态到Redis失败: {e}")
    
    def _load_state_from_redis(self):
        """启动时从Redis恢复校准状态"""
        if not self._redis_client:
            return
        
        try:
            state_json = self._redis_client.get("calibration:state")
            if state_json:
                state_data = json.loads(state_json)
                with self._lock:
                    for evaluator, stats_dict in state_data.get("evaluator_stats", {}).items():
                        stats = CalibrationStats()
                        stats.count = stats_dict.get("count", 0)
                        stats.mean_deviation = stats_dict.get("mean_deviation", 0.0)
                        stats.std_deviation = stats_dict.get("std_deviation", 0.0)
                        stats.max_deviation = stats_dict.get("max_deviation", 0.0)
                        stats.min_deviation = stats_dict.get("min_deviation", 0.0)
                        stats.last_updated = stats_dict.get("last_updated", 0.0)
                        stats.confidence_mean = stats_dict.get("confidence_mean", 0.0)
                        self._evaluator_stats[evaluator] = stats
                    
                    for evaluator, cache_dict in state_data.get("calibration_cache", {}).items():
                        self._calibration_cache[evaluator] = (
                            cache_dict["factor"],
                            cache_dict["timestamp"],
                        )
                    
                    for alert_dict in state_data.get("alerts", []):
                        alert = CalibrationAlert(
                            evaluator_type=alert_dict["evaluator_type"],
                            deviation=alert_dict["deviation"],
                            threshold=alert_dict["threshold"],
                            severity=alert_dict["severity"],
                            message=alert_dict["message"],
                            timestamp=alert_dict.get("timestamp", time.time()),
                        )
                        alert.resolved = alert_dict.get("resolved", False)
                        self._alerts.append(alert)
                
                logger.info("AdaptiveCalibrator状态已从Redis恢复")
        except Exception as e:
            logger.error(f"AdaptiveCalibrator从Redis加载状态失败: {e}")
    
    def _sync_state_from_redis(self):
        """定期同步校准状态"""
        if not self._redis_client:
            return
        
        try:
            state_json = self._redis_client.get("calibration:state")
            if state_json:
                state_data = json.loads(state_json)
                with self._lock:
                    for evaluator, cache_dict in state_data.get("calibration_cache", {}).items():
                        if evaluator not in self._calibration_cache or \
                           cache_dict["timestamp"] > self._calibration_cache.get(evaluator, (0, 0))[1]:
                            self._calibration_cache[evaluator] = (
                                cache_dict["factor"],
                                cache_dict["timestamp"],
                            )
        except Exception as e:
            logger.error(f"AdaptiveCalibrator同步状态失败: {e}")

    def reset(self):
        """重置校准器状态"""
        with self._lock:
            self._evaluator_stats.clear()
            self._alerts.clear()
            self._calibration_cache.clear()
            self._golden_calibration_cache.clear()
        
        self._save_state_to_redis()
        logger.info("AdaptiveCalibrator 已重置")

    @classmethod
    def get_instance(cls) -> "AdaptiveCalibrator":
        """获取单例实例"""
        return cls()


calibrator = AdaptiveCalibrator()