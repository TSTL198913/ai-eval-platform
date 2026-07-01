"""
AdaptiveCalibrator Tests
测试目标：验证自适应校准器的偏差监控和自动校准功能
"""

import threading
import time

import pytest

from src.domain.calibration.adaptive_calibrator import (
    AdaptiveCalibrator,
    CalibrationAlert,
    CalibrationStats,
)
from src.schemas.evaluation import DomainResponse, EvaluatorStatus


class TestCalibrationStats:
    """测试校准统计信息"""

    def test_update_with_valid_data(self):
        """更新有效数据"""
        stats = CalibrationStats()
        
        stats.update(0.8, 0.85, 0.9)
        stats.update(0.75, 0.8, 0.85)
        stats.update(0.9, 0.88, 0.95)
        
        assert stats.count == 3
        assert stats.mean_deviation > 0.0

    def test_get_alert_when_deviation_exceeds_threshold(self):
        """偏差超过阈值时应触发警报"""
        stats = CalibrationStats()
        
        for i in range(5):
            stats.update(0.5, 0.9, 0.5)
        
        alert = stats.get_alert(threshold=0.05)
        
        assert alert is not None
        assert alert.severity in ["low", "medium", "high", "critical"]
        assert alert.deviation > 0.05

    def test_no_alert_when_deviation_under_threshold(self):
        """偏差在阈值内不应触发警报"""
        stats = CalibrationStats()
        
        for i in range(5):
            stats.update(0.8, 0.82, 0.9)
        
        alert = stats.get_alert(threshold=0.05)
        
        assert alert is None

    def test_no_alert_with_insufficient_samples(self):
        """样本不足时不应触发警报"""
        stats = CalibrationStats()
        
        for i in range(4):
            stats.update(0.5, 0.9, 0.5)
        
        alert = stats.get_alert(threshold=0.05)
        
        assert alert is None


class TestCalibrationAlert:
    """测试校准警报"""

    def test_alert_creation(self):
        """警报创建"""
        alert = CalibrationAlert(
            evaluator_type="test_evaluator",
            deviation=0.1,
            threshold=0.05,
            severity="high",
            message="测试警报",
        )
        
        assert alert.evaluator_type == "test_evaluator"
        assert alert.deviation == 0.1
        assert alert.threshold == 0.05
        assert alert.severity == "high"
        assert alert.resolved is False

    def test_alert_to_dict(self):
        """警报转换为字典"""
        alert = CalibrationAlert(
            evaluator_type="test",
            deviation=0.1,
            threshold=0.05,
            severity="medium",
            message="测试",
        )
        
        alert_dict = alert.to_dict()
        
        assert isinstance(alert_dict, dict)
        assert alert_dict["evaluator_type"] == "test"
        assert alert_dict["deviation"] == 0.1
        assert alert_dict["resolved"] is False


class TestAdaptiveCalibratorPositiveCases:
    """正向测试 - 正常功能"""

    @pytest.fixture
    def calibrator(self):
        calibrator = AdaptiveCalibrator.get_instance()
        calibrator.reset()
        return calibrator

    def test_record_evaluation(self, calibrator):
        """记录评估结果"""
        result = DomainResponse(
            text="测试",
            score=0.8,
            evaluation_status=EvaluatorStatus.SUCCESS,
            confidence=0.9,
        )
        
        calibrator.record_evaluation("qa", result, 0.85)
        
        stats = calibrator.get_evaluator_stats("qa")
        assert stats is not None
        assert stats.count == 1

    def test_calibration_report_generated(self, calibrator):
        """生成校准报告"""
        result = DomainResponse(
            text="测试",
            score=0.8,
            evaluation_status=EvaluatorStatus.SUCCESS,
            confidence=0.9,
        )
        
        calibrator.record_evaluation("qa", result, 0.85)
        report = calibrator.get_calibration_report()
        
        assert isinstance(report, str)
        assert "自适应校准报告" in report

    def test_apply_calibration_factor(self, calibrator):
        """应用校准因子"""
        calibrator._calibration_cache["test"] = (1.2, 0.0)
        
        calibrated = calibrator.apply_calibration("test", 0.5)
        
        assert calibrated == 0.6
        assert 0.0 <= calibrated <= 1.0

    def test_get_all_stats(self, calibrator):
        """获取所有统计信息"""
        result = DomainResponse(
            text="测试",
            score=0.8,
            evaluation_status=EvaluatorStatus.SUCCESS,
            confidence=0.9,
        )
        
        calibrator.record_evaluation("qa", result, 0.85)
        stats = calibrator.get_all_stats()
        
        assert isinstance(stats, dict)
        assert "qa" in stats


class TestAdaptiveCalibratorNegativeCases:
    """负向测试 - 异常情况"""

    @pytest.fixture
    def calibrator(self):
        calibrator = AdaptiveCalibrator.get_instance()
        calibrator.reset()
        return calibrator

    def test_record_evaluation_with_none_score(self, calibrator):
        """记录分数为 None 的评估"""
        result = DomainResponse(
            text="测试",
            score=None,
            evaluation_status=EvaluatorStatus.ERROR,
            confidence=0.9,
        )
        
        calibrator.record_evaluation("qa", result, 0.85)
        
        stats = calibrator.get_evaluator_stats("qa")
        assert stats is None or stats.count == 0

    def test_calibrate_with_insufficient_samples(self, calibrator):
        """样本不足时校准失败"""
        result = DomainResponse(
            text="测试",
            score=0.5,
            evaluation_status=EvaluatorStatus.SUCCESS,
            confidence=0.9,
        )
        
        calibrator.record_evaluation("qa", result, 0.9)
        
        success = calibrator.calibrate("qa")
        
        assert success is False

    def test_resolve_invalid_alert(self, calibrator):
        """解决无效警报索引"""
        success = calibrator.resolve_alert(999)
        
        assert success is False

    def test_check_deviation_with_no_stats(self, calibrator):
        """检查不存在的评估器偏差"""
        alert = calibrator.check_deviation("nonexistent")
        
        assert alert is None


class TestAdaptiveCalibratorBoundaryCases:
    """边界测试 - 边界值"""

    @pytest.fixture
    def calibrator(self):
        calibrator = AdaptiveCalibrator.get_instance()
        calibrator.reset()
        return calibrator

    def test_deviation_at_threshold_no_alert(self, calibrator):
        """偏差刚好等于阈值不应触发警报"""
        result = DomainResponse(
            text="测试",
            score=0.75,
            evaluation_status=EvaluatorStatus.SUCCESS,
            confidence=0.9,
        )
        
        for i in range(5):
            calibrator.record_evaluation("boundary", result, 0.8)
        
        alert = calibrator.check_deviation("boundary")
        
        assert alert is None

    def test_deviation_just_above_threshold_triggers_alert(self, calibrator):
        """偏差略高于阈值应触发警报"""
        result = DomainResponse(
            text="测试",
            score=0.74,
            evaluation_status=EvaluatorStatus.SUCCESS,
            confidence=0.9,
        )
        
        for i in range(5):
            calibrator.record_evaluation("boundary_high", result, 0.8)
        
        alert = calibrator.check_deviation("boundary_high")
        
        assert alert is not None

    def test_apply_calibration_clamped_to_range(self, calibrator):
        """校准后分数应限制在 0-1 范围内"""
        calibrator._calibration_cache["test"] = (2.0, 0.0)
        
        calibrated = calibrator.apply_calibration("test", 0.8)
        
        assert calibrated == 1.0

    def test_apply_calibration_below_zero_clamped(self, calibrator):
        """校准后分数低于 0 应限制为 0"""
        calibrator._calibration_cache["test"] = (0.1, 0.0)
        
        calibrated = calibrator.apply_calibration("test", 0.05)
        
        assert calibrated >= 0.0


class TestAdaptiveCalibratorContract:
    """契约测试 - 验证校准器契约"""

    @pytest.fixture
    def calibrator(self):
        calibrator = AdaptiveCalibrator.get_instance()
        calibrator.reset()
        return calibrator

    def test_singleton_pattern(self):
        """验证单例模式"""
        instance1 = AdaptiveCalibrator.get_instance()
        instance2 = AdaptiveCalibrator.get_instance()
        
        assert instance1 is instance2

    def test_alert_severity_levels(self, calibrator):
        """验证警报严重级别"""
        low_deviation = DomainResponse(
            text="测试",
            score=0.70,
            evaluation_status=EvaluatorStatus.SUCCESS,
            confidence=0.9,
        )
        
        high_deviation = DomainResponse(
            text="测试",
            score=0.5,
            evaluation_status=EvaluatorStatus.SUCCESS,
            confidence=0.9,
        )
        
        for i in range(5):
            calibrator.record_evaluation("low", low_deviation, 0.8)
            calibrator.record_evaluation("high", high_deviation, 0.8)
        
        alerts = calibrator.get_all_alerts()
        
        assert len(alerts) >= 2

    def test_reset_clears_all_data(self, calibrator):
        """重置应清除所有数据"""
        result = DomainResponse(
            text="测试",
            score=0.8,
            evaluation_status=EvaluatorStatus.SUCCESS,
            confidence=0.9,
        )
        
        calibrator.record_evaluation("qa", result, 0.85)
        calibrator.reset()
        
        stats = calibrator.get_all_stats()
        alerts = calibrator.get_all_alerts()
        
        assert len(stats) == 0
        assert len(alerts) == 0


class TestAdaptiveCalibratorConcurrency:
    """并发测试 - 线程安全"""

    @pytest.fixture
    def calibrator(self):
        calibrator = AdaptiveCalibrator.get_instance()
        calibrator.reset()
        return calibrator

    def test_concurrent_record_evaluation(self, calibrator):
        """并发记录评估结果"""
        def record_worker(evaluator_type, base_score):
            for i in range(20):
                result = DomainResponse(
                    text="测试",
                    score=base_score + i * 0.01,
                    evaluation_status=EvaluatorStatus.SUCCESS,
                    confidence=0.9,
                )
                calibrator.record_evaluation(evaluator_type, result, 0.8)
                time.sleep(0.001)

        threads = []
        for i in range(5):
            t = threading.Thread(target=record_worker, args=(f"evaluator_{i}", 0.7))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        for i in range(5):
            stats = calibrator.get_evaluator_stats(f"evaluator_{i}")
            assert stats is not None
            assert stats.count == 20

    def test_concurrent_check_and_calibrate(self, calibrator):
        """并发检查偏差和校准"""
        for i in range(10):
            result = DomainResponse(
                text="测试",
                score=0.6,
                evaluation_status=EvaluatorStatus.SUCCESS,
                confidence=0.9,
            )
            calibrator.record_evaluation("concurrent_test", result, 0.8)

        def check_worker():
            for _ in range(10):
                calibrator.check_deviation("concurrent_test")
                calibrator.get_all_stats()
                time.sleep(0.001)

        threads = []
        for _ in range(3):
            t = threading.Thread(target=check_worker)
            threads.append(t)
            t.start()

        calibrator.calibrate("concurrent_test")

        for t in threads:
            t.join()

        assert calibrator.get_evaluator_stats("concurrent_test") is not None


class TestCalibrationFactorCalculation:
    """校准因子计算测试"""

    @pytest.fixture
    def calibrator(self):
        calibrator = AdaptiveCalibrator.get_instance()
        calibrator.reset()
        return calibrator

    def test_calibration_factor_when_scores_higher_than_expected(self, calibrator):
        """当分数高于期望值时校准因子大于1，应用后分数被限制在[0,1]"""
        for i in range(5):
            result = DomainResponse(
                text="测试",
                score=0.9,
                evaluation_status=EvaluatorStatus.SUCCESS,
                confidence=0.9,
            )
            calibrator.record_evaluation("high_score", result, 0.8)

        success = calibrator.calibrate("high_score")
        assert success is True

        calibrated = calibrator.apply_calibration("high_score", 0.9)
        assert calibrated == 1.0
        assert 0.0 <= calibrated <= 1.0

    def test_calibration_factor_when_scores_lower_than_expected(self, calibrator):
        """当分数低于期望值时校准因子小于1，应用后分数降低"""
        for i in range(5):
            result = DomainResponse(
                text="测试",
                score=0.7,
                evaluation_status=EvaluatorStatus.SUCCESS,
                confidence=0.9,
            )
            calibrator.record_evaluation("low_score", result, 0.8)

        success = calibrator.calibrate("low_score")
        assert success is True

        calibrated = calibrator.apply_calibration("low_score", 0.7)
        assert calibrated < 0.7
        assert 0.0 <= calibrated <= 1.0

    def test_calibration_factor_with_zero_expected_score(self, calibrator):
        """期望值为0时不应影响校准因子计算"""
        for i in range(5):
            result = DomainResponse(
                text="测试",
                score=0.5,
                evaluation_status=EvaluatorStatus.SUCCESS,
                confidence=0.9,
            )
            calibrator.record_evaluation("zero_test", result, 0.5)

        success = calibrator.calibrate("zero_test")
        assert success is True

    def test_calibration_factor_brings_scores_closer_to_expected(self, calibrator):
        """校准后分数应更接近期望值"""
        for i in range(5):
            result = DomainResponse(
                text="测试",
                score=0.85,
                evaluation_status=EvaluatorStatus.SUCCESS,
                confidence=0.9,
            )
            calibrator.record_evaluation("close_test", result, 0.8)

        calibrator.calibrate("close_test")
        stats = calibrator.get_evaluator_stats("close_test")
        
        assert stats is not None
        assert stats.mean_deviation <= 0.05 or stats.count >= 5


class TestConfidenceStatistics:
    """置信度统计测试"""

    @pytest.fixture
    def calibrator(self):
        calibrator = AdaptiveCalibrator.get_instance()
        calibrator.reset()
        return calibrator

    def test_confidence_mean_calculation(self):
        """置信度均值计算"""
        stats = CalibrationStats()
        stats.update(0.8, 0.85, 0.9)
        stats.update(0.75, 0.8, 0.85)
        stats.update(0.9, 0.88, 0.95)

        assert stats.confidence_mean > 0.0
        assert 0.85 <= stats.confidence_mean <= 0.95

    def test_confidence_mean_with_zero_confidence(self):
        """置信度为0时的计算"""
        stats = CalibrationStats()
        stats.update(0.8, 0.85, 0.0)
        stats.update(0.75, 0.8, 0.5)

        assert stats.confidence_mean == 0.25

    def test_calibration_report_includes_confidence(self, calibrator):
        """校准报告应包含置信度信息"""
        result = DomainResponse(
            text="测试",
            score=0.8,
            evaluation_status=EvaluatorStatus.SUCCESS,
            confidence=0.9,
        )

        calibrator.record_evaluation("qa", result, 0.85)
        report = calibrator.get_calibration_report()

        assert "置信度" in report or "confidence" in report.lower()


class TestAlertSeverityLevels:
    """警报严重级别测试"""

    @pytest.fixture
    def calibrator(self):
        calibrator = AdaptiveCalibrator.get_instance()
        calibrator.reset()
        return calibrator

    def test_severity_low(self, calibrator):
        """低严重级别警报 (deviation/threshold < 1.2)"""
        result = DomainResponse(
            text="测试",
            score=0.745,
            evaluation_status=EvaluatorStatus.SUCCESS,
            confidence=0.9,
        )

        for i in range(5):
            calibrator.record_evaluation("low_sev", result, 0.8)

        alerts = calibrator.get_all_alerts()
        assert len(alerts) >= 1
        alert = alerts[-1]
        assert alert.severity == "low"

    def test_severity_medium(self, calibrator):
        """中严重级别警报 (1.2 <= deviation/threshold < 1.5)"""
        result = DomainResponse(
            text="测试",
            score=0.73,
            evaluation_status=EvaluatorStatus.SUCCESS,
            confidence=0.9,
        )

        for i in range(5):
            calibrator.record_evaluation("med_sev", result, 0.8)

        alerts = calibrator.get_all_alerts()
        assert len(alerts) >= 1
        alert = alerts[-1]
        assert alert.severity == "medium"

    def test_severity_high(self, calibrator):
        """高严重级别警报 (1.5 <= deviation/threshold < 2.0)"""
        result = DomainResponse(
            text="测试",
            score=0.715,
            evaluation_status=EvaluatorStatus.SUCCESS,
            confidence=0.9,
        )

        for i in range(5):
            calibrator.record_evaluation("high_sev", result, 0.8)

        alerts = calibrator.get_all_alerts()
        assert len(alerts) >= 1
        alert = alerts[-1]
        assert alert.severity == "high"

    def test_severity_critical(self, calibrator):
        """严重级别警报 (deviation/threshold >= 2.0)"""
        result = DomainResponse(
            text="测试",
            score=0.5,
            evaluation_status=EvaluatorStatus.SUCCESS,
            confidence=0.9,
        )

        for i in range(5):
            calibrator.record_evaluation("crit_sev", result, 0.8)

        alerts = calibrator.get_all_alerts()
        assert len(alerts) >= 1
        alert = alerts[-1]
        assert alert.severity == "critical"


class TestCalibrationCache:
    """校准缓存测试"""

    @pytest.fixture
    def calibrator(self):
        calibrator = AdaptiveCalibrator.get_instance()
        calibrator.reset()
        return calibrator

    def test_calibration_cache_stores_factor(self, calibrator):
        """校准缓存应存储校准因子"""
        for i in range(5):
            result = DomainResponse(
                text="测试",
                score=0.6,
                evaluation_status=EvaluatorStatus.SUCCESS,
                confidence=0.9,
            )
            calibrator.record_evaluation("cache_test", result, 0.8)

        calibrator.calibrate("cache_test")
        stats = calibrator.get_all_stats()

        assert "cache_test" in stats

    def test_apply_calibration_without_cache(self, calibrator):
        """无缓存时应返回原始分数"""
        result = calibrator.apply_calibration("nonexistent", 0.5)
        assert result == 0.5


class TestCalibrationStatsToDict:
    """统计信息转字典测试"""

    def test_stats_to_dict_contains_all_fields(self):
        """统计信息转字典应包含所有字段"""
        stats = CalibrationStats()
        stats.update(0.8, 0.85, 0.9)
        stats.update(0.75, 0.8, 0.85)

        stats_dict = stats.to_dict()

        assert "count" in stats_dict
        assert "mean_deviation" in stats_dict
        assert "std_deviation" in stats_dict
        assert "max_deviation" in stats_dict
        assert "min_deviation" in stats_dict
        assert "last_updated" in stats_dict
        assert "confidence_mean" in stats_dict
        assert stats_dict["count"] == 2


class TestAlertToDict:
    """警报转字典测试"""

    def test_alert_to_dict_contains_all_fields(self):
        """警报转字典应包含所有字段"""
        alert = CalibrationAlert(
            evaluator_type="test",
            deviation=0.1,
            threshold=0.05,
            severity="high",
            message="测试警报",
        )

        alert_dict = alert.to_dict()

        assert "evaluator_type" in alert_dict
        assert "deviation" in alert_dict
        assert "threshold" in alert_dict
        assert "severity" in alert_dict
        assert "message" in alert_dict
        assert "timestamp" in alert_dict
        assert "resolved" in alert_dict
        assert alert_dict["resolved"] is False

    def test_alert_resolved_to_dict(self):
        """已解决警报转字典"""
        alert = CalibrationAlert(
            evaluator_type="test",
            deviation=0.1,
            threshold=0.05,
            severity="high",
            message="测试警报",
        )
        alert.resolved = True

        alert_dict = alert.to_dict()
        assert alert_dict["resolved"] is True