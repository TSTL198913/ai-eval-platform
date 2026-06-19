"""
自适应校准模块
在评估器执行前，先在黄金数据集上验证评估器准确性
如果偏差超过阈值，自动拒绝执行并提示校准
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

from src.domain.golden_dataset import golden_dataset_manager
from src.domain.evaluator_version import evaluator_version_manager, VersionStatus
from src.domain.statistical_analysis import statistical_analyzer


class CalibrationStatus(Enum):
    NOT_CALIBRATED = "not_calibrated"       # 未校准
    NO_VERSION = "no_version"               # 无版本注册
    CALIBRATING = "calibrating"             # 校准中
    CALIBRATED = "calibrated"               # 校准通过
    DRIFTED = "drifted"                     # 偏离校准
    REJECTED = "rejected"                   # 拒绝执行


@dataclass
class CalibrationResult:
    """校准结果"""
    evaluator_name: str
    evaluator_version: str
    dataset_name: str
    dataset_id: str

    # 校准数据
    n_samples: int
    gold_scores: List[float]      # 专家标准分数
    eval_scores: List[float]      # 评估器预测分数

    # 偏差分析
    mean_gold: float
    mean_eval: float
    mean_deviation: float        # 平均偏差
    max_deviation: float         # 最大偏差
    rmse: float                  # 均方根误差

    # 统计显著性
    correlation: float           # 与专家评分相关性
    is_calibrated: bool          # 是否通过校准
    deviation_threshold: float   # 偏差阈值
    confidence_interval: Tuple[float, float]  # 95%置信区间

    # 建议
    suggestions: List[str]

    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
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
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class PreExecutionCheck:
    """执行前检查结果"""
    evaluator_name: str
    evaluator_version: Optional[str]
    can_proceed: bool
    status: CalibrationStatus

    calibration_result: Optional[CalibrationResult] = None
    message: str = ""
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "evaluator_name": self.evaluator_name,
            "evaluator_version": self.evaluator_version,
            "can_proceed": self.can_proceed,
            "status": self.status.value,
            "message": self.message,
            "warnings": self.warnings
        }
        if self.calibration_result:
            result["calibration_result"] = self.calibration_result.to_dict()
        return result


class AdaptiveCalibrator:
    """自适应校准器"""

    def __init__(
        self,
        default_threshold: float = 5.0,  # 默认偏差阈值(%)
        min_calibration_samples: int = 5,  # 最少校准样本数
        calibration_interval: int = 24    # 校准有效期(小时)
    ):
        self._default_threshold = default_threshold
        self._min_calibration_samples = min_calibration_samples
        self._calibration_interval = calibration_interval
        self._calibration_cache: Dict[str, Dict[str, Any]] = {}
        self._load_cache()

    def _load_cache(self):
        """加载校准缓存"""
        cache_file = "data/calibration_cache.json"
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    self._calibration_cache = json.load(f)
            except Exception:
                pass

    def _save_cache(self):
        """保存校准缓存"""
        cache_file = "data/calibration_cache.json"
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(self._calibration_cache, f, ensure_ascii=False, indent=2)

    def _get_cache_key(self, evaluator_name: str, dataset_id: str) -> str:
        return f"{evaluator_name}:{dataset_id}"

    def _is_cache_valid(self, evaluator_name: str, dataset_id: str) -> bool:
        """检查缓存是否有效"""
        key = self._get_cache_key(evaluator_name, dataset_id)
        if key not in self._calibration_cache:
            return False

        cached = self._calibration_cache[key]
        cached_time = datetime.fromisoformat(cached["timestamp"])
        hours_elapsed = (datetime.utcnow() - cached_time).total_seconds() / 3600

        return hours_elapsed < self._calibration_interval

    def run_calibration(
        self,
        evaluator_name: str,
        evaluator_func: callable,
        dataset_id: str,
        threshold: float = None
    ) -> CalibrationResult:
        """在黄金数据集上运行校准

        Args:
            evaluator_name: 评估器名称
            evaluator_func: 评估函数 (接收一个样本，返回分数)
            dataset_id: 黄金数据集ID
            threshold: 偏差阈值 (默认使用系统配置)
        """
        dataset = golden_dataset_manager.get_dataset(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset '{dataset_id}' not found")

        samples = [s for s in dataset.samples if s.scores]
        if len(samples) < self._min_calibration_samples:
            raise ValueError(f"至少需要 {self._min_calibration_samples} 个带标注的样本")

        threshold = threshold or self._default_threshold

        # 获取评估器版本
        version_info = evaluator_version_manager.get_current_version(evaluator_name)
        evaluator_version = version_info.version if version_info else "unknown"

        gold_scores = []
        eval_scores = []
        suggestions = []

        for sample in samples:
            # 专家标准分数
            gold_score = sum(sample.scores.values()) / len(sample.scores)
            gold_scores.append(gold_score)

            # 评估器预测分数
            try:
                eval_result = evaluator_func(sample)
                eval_score = eval_result.get("score", eval_result.get("total_score", 0))
                eval_scores.append(eval_score)
            except Exception as e:
                suggestions.append(f"样本 {sample.id} 评估失败: {str(e)}")
                eval_scores.append(gold_score)  # 保守估计

        # 计算偏差
        mean_gold = sum(gold_scores) / len(gold_scores)
        mean_eval = sum(eval_scores) / len(eval_scores)
        mean_deviation = abs(mean_eval - mean_gold)
        max_deviation = max(abs(e - g) for e, g in zip(eval_scores, gold_scores))

        # RMSE
        import numpy as np
        rmse = np.sqrt(sum((e - g) ** 2 for e, g in zip(eval_scores, gold_scores)) / len(eval_scores))

        # 相关性
        if len(gold_scores) > 1:
            correlation = np.corrcoef(gold_scores, eval_scores)[0, 1]
        else:
            correlation = 1.0

        # 计算置信区间
        deviations = [abs(e - g) for e, g in zip(eval_scores, gold_scores)]
        ci_result = statistical_analyzer.calculate_confidence_interval(deviations, confidence=0.95)
        confidence_interval = (ci_result.lower, ci_result.upper)

        # 判断是否通过校准
        is_calibrated = mean_deviation <= threshold

        # 生成建议
        if mean_deviation > threshold:
            suggestions.append(f"评估器偏差 {mean_deviation:.2f} 超过阈值 {threshold}")
        if max_deviation > threshold * 2:
            suggestions.append(f"存在极端偏差样本 (最大偏差 {max_deviation:.2f})")
        if correlation < 0.7:
            suggestions.append(f"与专家评分相关性偏低 ({correlation:.2f})，建议检查评估逻辑")

        if is_calibrated:
            suggestions.append("校准通过，评估器可正常使用")

        result = CalibrationResult(
            evaluator_name=evaluator_name,
            evaluator_version=evaluator_version,
            dataset_name=dataset.name,
            dataset_id=dataset_id,
            n_samples=len(samples),
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
            suggestions=suggestions
        )

        # 更新缓存
        key = self._get_cache_key(evaluator_name, dataset_id)
        self._calibration_cache[key] = {
            "is_calibrated": is_calibrated,
            "mean_deviation": mean_deviation,
            "timestamp": datetime.utcnow().isoformat()
        }
        self._save_cache()

        # 更新评估器版本的校准分数
        evaluator_version_manager.update_calibration(evaluator_name, mean_eval)

        return result

    def pre_execution_check(
        self,
        evaluator_name: str,
        dataset_id: str = None
    ) -> PreExecutionCheck:
        """执行前检查

        Returns:
            PreExecutionCheck: 检查结果，决定是否允许执行评估
        """
        warnings = []

        # 检查是否有版本注册
        version_info = evaluator_version_manager.get_current_version(evaluator_name)
        if not version_info:
            return PreExecutionCheck(
                evaluator_name=evaluator_name,
                evaluator_version=None,
                can_proceed=True,  # 允许执行，但给出警告
                status=CalibrationStatus.NO_VERSION,
                message="评估器未注册版本，建议先注册版本",
                warnings=["评估结果可能不可靠", "建议先在黄金数据集上校准"]
            )
        else:
            evaluator_version = version_info.version

        # 如果没有指定数据集，检查缓存
        if dataset_id:
            if not self._is_cache_valid(evaluator_name, dataset_id):
                return PreExecutionCheck(
                    evaluator_name=evaluator_name,
                    evaluator_version=evaluator_version,
                    can_proceed=False,
                    status=CalibrationStatus.NOT_CALIBRATED,
                    message=f"评估器尚未在数据集 {dataset_id} 上校准，或校准已过期"
                )

            # 检查缓存中的校准状态
            key = self._get_cache_key(evaluator_name, dataset_id)
            cached = self._calibration_cache.get(key, {})
            is_calibrated = cached.get("is_calibrated", False)

            if is_calibrated:
                return PreExecutionCheck(
                    evaluator_name=evaluator_name,
                    evaluator_version=evaluator_version,
                    can_proceed=True,
                    status=CalibrationStatus.CALIBRATED,
                    message="校准检查通过"
                )
            else:
                mean_deviation = cached.get("mean_deviation", 0)
                return PreExecutionCheck(
                    evaluator_name=evaluator_name,
                    evaluator_version=evaluator_version,
                    can_proceed=False,
                    status=CalibrationStatus.DRIFTED,
                    message=f"评估器偏差 {mean_deviation:.2f} 超过阈值，需要重新校准",
                    warnings=["评估器已偏离校准区间"]
                )

        # 没有指定数据集，检查全局校准状态
        calibration_status = evaluator_version_manager.check_calibration_status(evaluator_name)
        can_proceed = calibration_status.get("can_proceed", True)

        if not calibration_status.get("calibration_score"):
            return PreExecutionCheck(
                evaluator_name=evaluator_name,
                evaluator_version=evaluator_version,
                can_proceed=True,  # 允许执行，但会提示
                status=CalibrationStatus.NOT_CALIBRATED,
                message="评估器尚未校准，建议先在黄金数据集上校准",
                warnings=["评估结果可能不可靠"]
            )

        if not can_proceed:
            return PreExecutionCheck(
                evaluator_name=evaluator_name,
                evaluator_version=evaluator_version,
                can_proceed=False,
                status=CalibrationStatus.DRIFTED,
                message="评估器偏离校准区间，系统拒绝执行"
            )

        return PreExecutionCheck(
            evaluator_name=evaluator_name,
            evaluator_version=evaluator_version,
            can_proceed=True,
            status=CalibrationStatus.CALIBRATED,
            message="校准检查通过"
        )

    def get_calibration_report(self, evaluator_name: str) -> Dict[str, Any]:
        """获取校准报告"""
        version_info = evaluator_version_manager.get_current_version(evaluator_name)

        return {
            "evaluator_name": evaluator_name,
            "version": version_info.version if version_info else "unknown",
            "calibration_history": evaluator_version_manager.get_version_history(evaluator_name),
            "calibration_status": evaluator_version_manager.check_calibration_status(evaluator_name),
            "cached_datasets": [
                {
                    "dataset_id": k.split(":")[1],
                    "is_calibrated": v.get("is_calibrated"),
                    "mean_deviation": v.get("mean_deviation"),
                    "timestamp": v.get("timestamp")
                }
                for k, v in self._calibration_cache.items()
                if k.startswith(f"{evaluator_name}:")
            ],
            "recommendations": self._generate_recommendations(evaluator_name)
        }

    def _generate_recommendations(self, evaluator_name: str) -> List[str]:
        """生成校准建议"""
        recommendations = []
        status = evaluator_version_manager.check_calibration_status(evaluator_name)

        if status.get("status") == "drifted":
            recommendations.append("立即对评估器进行重新校准")
            recommendations.append("检查评估器最近的代码变更")
        elif status.get("status") == "not_calibrated":
            recommendations.append("建议使用黄金数据集对评估器进行首次校准")
        else:
            recommendations.append("评估器状态正常")

        datasets = golden_dataset_manager.list_datasets()
        if datasets:
            recommendations.append(f"可用的黄金数据集: {', '.join([d.name for d in datasets[:3]])}")

        return recommendations


# 全局实例
adaptive_calibrator = AdaptiveCalibrator()
