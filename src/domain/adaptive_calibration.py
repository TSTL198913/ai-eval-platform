"""
兼容性导入层 - 自适应校准模块

实际模块位于 src/domain/calibration/adaptive_calibrator.py
此文件为向后兼容的导入层
"""

from src.domain.calibration.adaptive_calibrator import (
    AdaptiveCalibrator,
    CalibrationAlert,
    CalibrationResult,
    CalibrationStats,
    CalibrationStatus,
    PreExecutionCheck,
    calibrator,
)
from src.domain.golden_dataset import golden_dataset_manager
from src.domain.evaluator_version import evaluator_version_manager

__all__ = [
    "AdaptiveCalibrator",
    "CalibrationAlert",
    "CalibrationResult",
    "CalibrationStats",
    "CalibrationStatus",
    "PreExecutionCheck",
    "calibrator",
    "golden_dataset_manager",
    "evaluator_version_manager",
]
