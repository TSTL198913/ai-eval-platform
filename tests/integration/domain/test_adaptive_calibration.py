"""
自适应校准模块测试
测试目标：验证AdaptiveCalibrator的核心功能
核心功能：
1. 在黄金数据集上运行校准
2. 计算评估器与专家标准的偏差
3. 执行前检查评估器状态
4. 缓存管理

关键发现：（测试过程中记录）
"""

import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.adaptive_calibration import (
    AdaptiveCalibrator,
    CalibrationResult,
    CalibrationStatus,
    PreExecutionCheck,
)


class TestAdaptiveCalibratorInitialization:
    """自适应校准器初始化测试"""

    def test_initialization_with_default_values(self):
        """使用默认值初始化"""
        calibrator = AdaptiveCalibrator()

        assert calibrator._default_threshold == 5.0
        assert calibrator._min_calibration_samples == 5
        assert calibrator._calibration_interval == 24

    def test_initialization_with_custom_values(self):
        """使用自定义值初始化"""
        calibrator = AdaptiveCalibrator(
            default_threshold=10.0, min_calibration_samples=10, calibration_interval=48
        )

        assert calibrator._default_threshold == 10.0
        assert calibrator._min_calibration_samples == 10
        assert calibrator._calibration_interval == 48


class TestAdaptiveCalibratorRunCalibration:
    """校准运行测试 - 核心功能"""

    @pytest.fixture
    def calibrator(self):
        """创建测试用校准器"""
        temp_dir = tempfile.mkdtemp()
        calibrator = AdaptiveCalibrator()
        calibrator._calibration_cache = {}
        yield calibrator
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def mock_golden_dataset(self):
        """模拟黄金数据集"""
        dataset = MagicMock()
        samples = []

        # 创建带评分的样本
        for i in range(5):
            sample = MagicMock()
            sample.id = f"sample_{i:03d}"
            sample.scores = {
                "correctness": 90 + i * 2,  # 90, 92, 94, 96, 98
                "completeness": 85 + i,  # 85, 86, 87, 88, 89
            }
            samples.append(sample)

        dataset.samples = samples
        dataset.name = "test_golden_dataset"
        return dataset

    def test_run_calibration_calculates_deviation(self, calibrator, mock_golden_dataset):
        """校准应计算偏差"""
        with patch("src.domain.adaptive_calibration.golden_dataset_manager") as mock_manager:
            mock_manager.get_dataset.return_value = mock_golden_dataset

            def mock_evaluate_fn(sample):
                # 模拟评估器预测（比专家低5分）
                return {"score": sum(sample.scores.values()) / len(sample.scores) - 5}

            result = calibrator.run_calibration(
                evaluator_name="test_evaluator",
                evaluator_func=mock_evaluate_fn,
                dataset_id="test_dataset_id",
            )

            assert isinstance(result, CalibrationResult)
            assert result.evaluator_name == "test_evaluator"
            assert result.mean_gold > result.mean_eval  # 专家分数应高于评估器

    def test_run_calibration_detects_calibration_pass(self, calibrator, mock_golden_dataset):
        """校准应检测校准通过（偏差<阈值）"""
        with patch("src.domain.adaptive_calibration.golden_dataset_manager") as mock_manager:
            mock_manager.get_dataset.return_value = mock_golden_dataset

            def mock_evaluate_fn(sample):
                # 模拟评估器预测（与专家非常接近）
                return {"score": sum(sample.scores.values()) / len(sample.scores)}

            result = calibrator.run_calibration(
                evaluator_name="test_evaluator",
                evaluator_func=mock_evaluate_fn,
                dataset_id="test_dataset_id",
                threshold=5.0,
            )

            # 当评估器与专家完全一致时，mean_deviation=0
            assert result.mean_deviation == 0.0
            assert result.is_calibrated is True

    def test_run_calibration_detects_drift(self, calibrator, mock_golden_dataset):
        """校准应检测到漂移（偏差>阈值）"""
        with patch("src.domain.adaptive_calibration.golden_dataset_manager") as mock_manager:
            mock_manager.get_dataset.return_value = mock_golden_dataset

            def mock_evaluate_fn(sample):
                # 模拟评估器预测（比专家高20分 - 严重漂移）
                return {"score": sum(sample.scores.values()) / len(sample.scores) + 20}

            result = calibrator.run_calibration(
                evaluator_name="test_evaluator",
                evaluator_func=mock_evaluate_fn,
                dataset_id="test_dataset_id",
                threshold=5.0,
            )

            assert result.mean_deviation > 5.0
            assert result.is_calibrated is False
            assert len(result.suggestions) > 0

    def test_run_calibration_calculates_rmse(self, calibrator, mock_golden_dataset):
        """校准应计算均方根误差"""
        with patch("src.domain.adaptive_calibration.golden_dataset_manager") as mock_manager:
            mock_manager.get_dataset.return_value = mock_golden_dataset

            def mock_evaluate_fn(sample):
                return {"score": sum(sample.scores.values()) / len(sample.scores) - 5}

            result = calibrator.run_calibration(
                evaluator_name="test_evaluator",
                evaluator_func=mock_evaluate_fn,
                dataset_id="test_dataset_id",
            )

            assert result.rmse > 0  # RMSE应该大于0
            assert isinstance(result.rmse, float)

    def test_run_calibration_calculates_correlation(self, calibrator, mock_golden_dataset):
        """校准应计算与专家评分的相关性"""
        with patch("src.domain.adaptive_calibration.golden_dataset_manager") as mock_manager:
            mock_manager.get_dataset.return_value = mock_golden_dataset

            def mock_evaluate_fn(sample):
                # 完全一致的预测应该相关性为1
                return {"score": sum(sample.scores.values()) / len(sample.scores)}

            result = calibrator.run_calibration(
                evaluator_name="test_evaluator",
                evaluator_func=mock_evaluate_fn,
                dataset_id="test_dataset_id",
            )

            assert result.correlation == 1.0  # 完全相关

    def test_run_calibration_insufficient_samples_raises(self, calibrator, mock_golden_dataset):
        """样本不足应抛出异常"""
        # 只保留2个样本（少于min_calibration_samples=5）
        mock_golden_dataset.samples = mock_golden_dataset.samples[:2]

        with patch("src.domain.adaptive_calibration.golden_dataset_manager") as mock_manager:
            mock_manager.get_dataset.return_value = mock_golden_dataset

            with pytest.raises(ValueError, match="至少需要"):
                calibrator.run_calibration(
                    evaluator_name="test_evaluator",
                    evaluator_func=lambda x: {"score": 80},
                    dataset_id="test_dataset_id",
                )

    def test_run_calibration_dataset_not_found_raises(self, calibrator):
        """数据集不存在应抛出异常"""
        with patch("src.domain.adaptive_calibration.golden_dataset_manager") as mock_manager:
            mock_manager.get_dataset.return_value = None

            with pytest.raises(ValueError, match="Dataset.*not found"):
                calibrator.run_calibration(
                    evaluator_name="test_evaluator",
                    evaluator_func=lambda x: {"score": 80},
                    dataset_id="nonexistent_id",
                )


class TestAdaptiveCalibratorPreExecutionCheck:
    """执行前检查测试 - 核心功能"""

    @pytest.fixture
    def calibrator(self):
        """创建测试用校准器"""
        temp_dir = tempfile.mkdtemp()
        calibrator = AdaptiveCalibrator()
        calibrator._calibration_cache = {}
        yield calibrator
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_pre_execution_check_no_version_warns(self, calibrator):
        """无版本注册应警告"""
        with patch("src.domain.adaptive_calibration.evaluator_version_manager") as mock_version_mgr:
            mock_version_mgr.get_current_version.return_value = None

            check = calibrator.pre_execution_check("test_evaluator")

            assert check.can_proceed is True
            assert check.status == CalibrationStatus.NO_VERSION  # 无版本时返回NO_VERSION状态
            assert "未注册版本" in check.message
            assert "评估结果可能不可靠" in check.warnings

    def test_pre_execution_check_calibrated_allows_proceed(self, calibrator):
        """校准通过应允许执行"""
        calibrator._calibration_cache = {
            "test_evaluator:test_dataset": {
                "is_calibrated": True,
                "mean_deviation": 3.0,
                "timestamp": datetime.utcnow().isoformat(),
            }
        }

        with patch("src.domain.adaptive_calibration.evaluator_version_manager") as mock_version_mgr:
            mock_version_mgr.get_current_version.return_value = MagicMock(version="1.0.0")

            check = calibrator.pre_execution_check("test_evaluator", dataset_id="test_dataset")

            assert check.can_proceed is True
            assert check.status == CalibrationStatus.CALIBRATED

    def test_pre_execution_check_drifted_rejects(self, calibrator):
        """漂移应拒绝执行"""
        calibrator._calibration_cache = {
            "test_evaluator:test_dataset": {
                "is_calibrated": False,
                "mean_deviation": 8.0,  # 超过阈值
                "timestamp": datetime.utcnow().isoformat(),
            }
        }

        with patch("src.domain.adaptive_calibration.evaluator_version_manager") as mock_version_mgr:
            mock_version_mgr.get_current_version.return_value = MagicMock(version="1.0.0")

            check = calibrator.pre_execution_check("test_evaluator", dataset_id="test_dataset")

            assert check.can_proceed is False
            assert check.status == CalibrationStatus.DRIFTED
            assert "需要重新校准" in check.message

    def test_pre_execution_check_cache_expired(self, calibrator):
        """缓存过期应重新校准"""
        # 设置25小时前的缓存（超过24小时）
        past_time = (datetime.utcnow() - timedelta(hours=25)).isoformat()
        calibrator._calibration_cache = {
            "test_evaluator:test_dataset": {
                "is_calibrated": True,
                "mean_deviation": 3.0,
                "timestamp": past_time,
            }
        }

        with patch("src.domain.adaptive_calibration.evaluator_version_manager") as mock_version_mgr:
            mock_version_mgr.get_current_version.return_value = MagicMock(version="1.0.0")

            check = calibrator.pre_execution_check("test_evaluator", dataset_id="test_dataset")

            assert check.can_proceed is False
            assert check.status == CalibrationStatus.NOT_CALIBRATED


class TestCalibrationResult:
    """校准结果数据类测试"""

    def test_calibration_result_to_dict(self):
        """校准结果转字典"""
        result = CalibrationResult(
            evaluator_name="test_evaluator",
            evaluator_version="1.0.0",
            dataset_name="test_dataset",
            dataset_id="test_id",
            n_samples=5,
            gold_scores=[90, 92, 94, 96, 98],
            eval_scores=[88, 90, 92, 94, 96],
            mean_gold=94.0,
            mean_eval=92.0,
            mean_deviation=2.0,
            max_deviation=2.0,
            rmse=0.02,
            correlation=0.99,
            is_calibrated=True,
            deviation_threshold=5.0,
            confidence_interval=(1.0, 3.0),
            suggestions=["校准通过"],
        )

        result_dict = result.to_dict()

        assert result_dict["evaluator_name"] == "test_evaluator"
        assert result_dict["is_calibrated"] is True
        assert result_dict["mean_deviation"] == 2.0
        assert result_dict["correlation"] == 0.99


class TestPreExecutionCheck:
    """执行前检查结果数据类测试"""

    def test_pre_execution_check_to_dict(self):
        """执行前检查结果转字典"""
        check = PreExecutionCheck(
            evaluator_name="test_evaluator",
            evaluator_version="1.0.0",
            can_proceed=True,
            status=CalibrationStatus.CALIBRATED,
            message="校准检查通过",
            warnings=["warning1"],
        )

        check_dict = check.to_dict()

        assert check_dict["evaluator_name"] == "test_evaluator"
        assert check_dict["can_proceed"] is True
        assert check_dict["status"] == "calibrated"
        assert check_dict["warnings"] == ["warning1"]


class TestCalibrationStatus:
    """校准状态枚举测试"""

    def test_calibration_status_values(self):
        """校准状态枚举值"""
        assert CalibrationStatus.NOT_CALIBRATED.value == "not_calibrated"
        assert CalibrationStatus.CALIBRATING.value == "calibrating"
        assert CalibrationStatus.CALIBRATED.value == "calibrated"
        assert CalibrationStatus.DRIFTED.value == "drifted"
        assert CalibrationStatus.REJECTED.value == "rejected"


class TestAdaptiveCalibratorCacheManagement:
    """缓存管理测试"""

    @pytest.fixture
    def calibrator(self):
        """创建测试用校准器"""
        calibrator = AdaptiveCalibrator()
        calibrator._calibration_cache = {}
        return calibrator

    def test_cache_key_generation(self, calibrator):
        """缓存键生成"""
        key = calibrator._get_cache_key("evaluator_name", "dataset_id")
        assert key == "evaluator_name:dataset_id"

    def test_is_cache_valid_true(self, calibrator):
        """有效缓存应返回True"""
        calibrator._calibration_cache = {
            "evaluator_name:dataset_id": {"timestamp": datetime.utcnow().isoformat()}
        }

        result = calibrator._is_cache_valid("evaluator_name", "dataset_id")

        assert result is True

    def test_is_cache_valid_false_expired(self, calibrator):
        """过期缓存应返回False"""
        past_time = (datetime.utcnow() - timedelta(hours=25)).isoformat()
        calibrator._calibration_cache = {"evaluator_name:dataset_id": {"timestamp": past_time}}

        result = calibrator._is_cache_valid("evaluator_name", "dataset_id")

        assert result is False

    def test_is_cache_valid_false_not_exist(self, calibrator):
        """不存在的缓存应返回False"""
        result = calibrator._is_cache_valid("nonexistent", "dataset_id")
        assert result is False


class TestAdaptiveCalibratorRecommendations:
    """校准建议生成测试"""

    @pytest.fixture
    def calibrator(self):
        """创建测试用校准器"""
        calibrator = AdaptiveCalibrator()
        calibrator._calibration_cache = {}
        return calibrator

    def test_generate_recommendations_drifted(self, calibrator):
        """漂移状态应生成立即重新校准建议"""
        with patch("src.domain.adaptive_calibration.evaluator_version_manager") as mock_version_mgr:
            mock_version_mgr.check_calibration_status.return_value = {"status": "drifted"}

            recommendations = calibrator._generate_recommendations("test_evaluator")

            assert any("重新校准" in r for r in recommendations)

    def test_generate_recommendations_not_calibrated(self, calibrator):
        """未校准状态应生成校准建议"""
        with patch("src.domain.adaptive_calibration.evaluator_version_manager") as mock_version_mgr:
            mock_version_mgr.check_calibration_status.return_value = {"status": "not_calibrated"}

            recommendations = calibrator._generate_recommendations("test_evaluator")

            assert any("校准" in r for r in recommendations)


# 关键发现：
# 1. 校准阈值默认5%，可配置
# 2. 缓存有效期默认24小时
# 3. 最少需要5个样本进行校准
# 4. 评估器完全一致时，correlation=1.0，mean_deviation=0
# 5. 漂移时会生成建议并拒绝执行
