"""
回归测试：收敛验证 - 评估失败样本不应产生0偏差
BUG-013: 假收敛 - 样本评估失败时错误地返回0偏差，导致假收敛

测试场景覆盖：
1. 正向：全部样本评估成功，正常计算偏差
2. 负向：全部样本评估失败，n_samples=0，is_calibrated=False
3. 边界：部分样本失败、部分成功，只计算成功样本的偏差
4. 边界：有效样本不足，返回无法校准
5. 异常：评估函数抛出各种异常，不应影响其他样本
6. 负向：失败样本不应填充黄金分数，避免虚假收敛
"""

import pytest
from unittest.mock import patch


class TestGoldenCalibrationFailureHandling:
    """黄金数据集校准 - 评估失败处理回归测试"""

    @pytest.fixture
    def test_dataset(self):
        """创建测试数据集并注入全局 golden_dataset_manager"""
        from src.domain.golden_dataset import golden_dataset_manager, GoldenSample, GoldenDataset
        from datetime import datetime

        dataset_id = "test_calib_ds"
        samples = []
        for i in range(10):
            samples.append(
                GoldenSample(
                    id=f"sample_{i}",
                    user_input=f"问题{i}",
                    actual_output=f"回答{i}",
                    expected_output=f"标准答案{i}",
                    scores={"overall": float(70 + i * 3)},
                )
            )

        dataset = GoldenDataset(
            id=dataset_id,
            name="测试校准数据集",
            description="用于校准失败测试",
            category="test_calibration",
            samples=samples,
        )

        with patch.object(golden_dataset_manager, "_datasets", {dataset_id: dataset}):
            with patch.object(golden_dataset_manager, "_sample_index",
                              {s.id: s for s in samples}):
                yield dataset_id

    def test_all_samples_succeed_normal_deviation(self, test_dataset):
        """正向：全部样本评估成功，正常计算偏差"""
        from src.domain.calibration.adaptive_calibrator import AdaptiveCalibrator

        calibrator = AdaptiveCalibrator()

        def perfect_eval(sample):
            gold = sum(sample.scores.values()) / len(sample.scores)
            return {"score": gold, "evaluation_status": "success"}

        result = calibrator.run_golden_calibration(
            evaluator_name="test_evaluator",
            evaluator_func=perfect_eval,
            dataset_id=test_dataset,
        )

        assert result.mean_deviation == pytest.approx(0.0, abs=0.01)
        assert result.n_samples == 10
        assert result.is_calibrated is True

    def test_all_samples_fail_returns_zero_effective(self, test_dataset):
        """负向：全部样本评估失败，有效样本数为0，is_calibrated=False"""
        from src.domain.calibration.adaptive_calibrator import AdaptiveCalibrator

        calibrator = AdaptiveCalibrator()

        def always_fail(sample):
            raise RuntimeError("评估失败")

        result = calibrator.run_golden_calibration(
            evaluator_name="test_evaluator",
            evaluator_func=always_fail,
            dataset_id=test_dataset,
        )

        assert result.n_samples == 0, "全部失败时有效样本数应为0"
        assert result.is_calibrated is False, "全部失败时不应判定为已校准"
        assert len(result.suggestions) >= 10, "应记录每个失败样本的错误"

    def test_partial_samples_fail_only_count_success(self, test_dataset):
        """边界：部分样本失败，只计算成功样本的偏差，n_samples 为有效样本数"""
        from src.domain.calibration.adaptive_calibrator import AdaptiveCalibrator

        calibrator = AdaptiveCalibrator()

        fail_set = {0, 3, 7}

        def partial_eval(sample):
            idx = int(sample.id.split("_")[1])
            if idx in fail_set:
                raise ValueError(f"样本{idx}失败")
            gold = sum(sample.scores.values()) / len(sample.scores)
            return {"score": gold * 0.95, "evaluation_status": "success"}

        result = calibrator.run_golden_calibration(
            evaluator_name="test_evaluator",
            evaluator_func=partial_eval,
            dataset_id=test_dataset,
        )

        expected_success = 10 - len(fail_set)
        assert result.n_samples == expected_success, f"有效样本数应为{expected_success}"
        assert result.mean_deviation > 0, "存在偏差时 mean_deviation 应 > 0"
        assert len(result.suggestions) >= len(fail_set), "应记录失败样本的建议"
        has_fail_msg = any("失败" in s for s in result.suggestions)
        assert has_fail_msg, "建议中应包含失败样本提示"

    def test_insufficient_valid_samples_returns_not_calibrated(self, test_dataset):
        """边界：有效样本不足最小要求，is_calibrated=False，n_samples=0 表示不可校准"""
        from src.domain.calibration.adaptive_calibrator import AdaptiveCalibrator

        calibrator = AdaptiveCalibrator()

        def mostly_fail(sample):
            idx = int(sample.id.split("_")[1])
            if idx == 0:
                return {"score": 0.8, "evaluation_status": "success"}
            raise RuntimeError("失败")

        result = calibrator.run_golden_calibration(
            evaluator_name="test_evaluator",
            evaluator_func=mostly_fail,
            dataset_id=test_dataset,
        )

        assert result.is_calibrated is False, "有效样本不足时不应判定为已校准"
        assert result.n_samples == 0, "有效样本不足时 n_samples 应为0，表示不可校准"
        assert any("有效样本不足" in s for s in result.suggestions), "建议中应包含有效样本不足提示"

    def test_failed_samples_not_padded_with_gold_score(self, test_dataset):
        """负向：失败样本不应填充黄金分数，避免虚假收敛"""
        from src.domain.calibration.adaptive_calibrator import AdaptiveCalibrator

        calibrator = AdaptiveCalibrator()

        def mostly_fail(sample):
            idx = int(sample.id.split("_")[1])
            if idx < 7:
                gold = sum(sample.scores.values()) / len(sample.scores)
                return {"score": gold + 20.0, "evaluation_status": "success"}
            raise RuntimeError("失败")

        result = calibrator.run_golden_calibration(
            evaluator_name="test_evaluator",
            evaluator_func=mostly_fail,
            dataset_id=test_dataset,
        )

        assert result.n_samples == 7
        assert result.mean_deviation > 15, "偏差不应被失败样本稀释"
        assert result.is_calibrated is False, "偏差过大不应判定为已校准"
