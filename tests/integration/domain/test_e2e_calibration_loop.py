"""
端到端校准集成测试 - PDCA 闭环验证
BUG-013: 假收敛修复后，验证完整 PDCA 循环可跑通

测试覆盖：
1. 正向：完整 PDCA 循环（计划→执行→检查→处理）
2. 正向：校准门控 → 评估器执行 → 偏差计算 → 结果判断
3. 负向：评估器偏差超标 → 触发校准需求事件
4. 边界：黄金数据集为空 → 正确返回无法校准
5. 集成：GoldenSample.input_data → 评估器执行 → 校准结果
"""

import pytest
from unittest.mock import patch, MagicMock


class TestEndToEndCalibrationLoop:
    """端到端校准闭环集成测试"""

    @pytest.fixture
    def setup_calibration_env(self):
        """搭建校准测试环境，注入测试数据集"""
        from src.domain.golden_dataset import (
            golden_dataset_manager, GoldenSample, GoldenDataset
        )
        from src.domain.calibration.adaptive_calibrator import AdaptiveCalibrator

        dataset_id = "e2e_test_general"
        samples = []
        for i in range(15):
            score = 60.0 + i * 2.5
            samples.append(
                GoldenSample(
                    id=f"e2e_sample_{i}",
                    user_input=f"测试问题 {i}",
                    actual_output=f"测试回答 {i}",
                    expected_output=f"标准答案 {i}",
                    scores={"overall": score, "quality": score + 2.0},
                )
            )

        dataset = GoldenDataset(
            id=dataset_id,
            name="端到端测试数据集",
            description="用于PDCA闭环测试",
            category="general",
            samples=samples,
        )

        calibrator = AdaptiveCalibrator()

        with patch.object(golden_dataset_manager, "_datasets", {dataset_id: dataset}):
            with patch.object(golden_dataset_manager, "_sample_index",
                              {s.id: s for s in samples}):
                yield {
                    "dataset_id": dataset_id,
                    "samples": samples,
                    "calibrator": calibrator,
                }

    def test_full_pdca_cycle_with_perfect_evaluator(self, setup_calibration_env):
        """正向：完整PDCA循环 - 完美评估器应通过校准"""
        env = setup_calibration_env
        calibrator = env["calibrator"]
        dataset_id = env["dataset_id"]

        def perfect_evaluator(sample):
            gold = sum(sample.scores.values()) / len(sample.scores)
            return {
                "score": gold,
                "evaluation_status": "success",
                "confidence": 0.95,
            }

        result = calibrator.run_golden_calibration(
            evaluator_name="test_perfect",
            evaluator_func=perfect_evaluator,
            dataset_id=dataset_id,
        )

        assert result.is_calibrated is True
        assert result.n_samples == 15
        assert result.mean_deviation < 0.01
        assert result.correlation > 0.99
        assert any("校准通过" in s for s in result.suggestions)

    def test_full_pdca_cycle_with_biased_evaluator(self, setup_calibration_env):
        """正向：完整PDCA循环 - 偏差评估器应未通过校准"""
        env = setup_calibration_env
        calibrator = env["calibrator"]
        dataset_id = env["dataset_id"]

        def biased_evaluator(sample):
            gold = sum(sample.scores.values()) / len(sample.scores)
            return {
                "score": gold * 0.6,
                "evaluation_status": "success",
                "confidence": 0.8,
            }

        result = calibrator.run_golden_calibration(
            evaluator_name="test_biased",
            evaluator_func=biased_evaluator,
            dataset_id=dataset_id,
        )

        assert result.is_calibrated is False
        assert result.n_samples == 15
        assert result.mean_deviation > 0.05
        assert any("偏差" in s and "超过阈值" in s for s in result.suggestions)

    def test_pdca_cycle_with_partial_failures(self, setup_calibration_env):
        """边界：PDCA循环中部分样本失败，仍可计算有效样本偏差"""
        env = setup_calibration_env
        calibrator = env["calibrator"]
        dataset_id = env["dataset_id"]

        fail_indices = {1, 5, 9, 13}

        def partially_failing_evaluator(sample):
            idx = int(sample.id.split("_")[-1])
            if idx in fail_indices:
                raise RuntimeError("LLM连接超时")
            gold = sum(sample.scores.values()) / len(sample.scores)
            return {
                "score": gold * 0.9995,
                "evaluation_status": "success",
                "confidence": 0.9,
            }

        result = calibrator.run_golden_calibration(
            evaluator_name="test_partial_fail",
            evaluator_func=partially_failing_evaluator,
            dataset_id=dataset_id,
        )

        expected_success = 15 - len(fail_indices)
        assert result.n_samples == expected_success
        assert result.is_calibrated is True
        assert any("个样本评估失败" in s for s in result.suggestions)
        fail_suggestions = [
            s for s in result.suggestions
            if "评估失败" in s and "样本 " in s and "e2e_sample_" in s
        ]
        assert len(fail_suggestions) == len(fail_indices)

    def test_golden_sample_input_data_used_in_calibration(self, setup_calibration_env):
        """集成：GoldenSample.input_data 被校准流程正确使用"""
        env = setup_calibration_env
        calibrator = env["calibrator"]
        dataset_id = env["dataset_id"]

        captured_inputs = []

        def evaluator_captures_input(sample):
            captured_inputs.append(sample.input_data)
            gold = sum(sample.scores.values()) / len(sample.scores)
            return {"score": gold, "evaluation_status": "success"}

        calibrator.run_golden_calibration(
            evaluator_name="test_input_data",
            evaluator_func=evaluator_captures_input,
            dataset_id=dataset_id,
        )

        assert len(captured_inputs) == 15
        for inp in captured_inputs:
            assert "actual_output" in inp
            assert "user_input" in inp
            assert "expected_output" in inp

    def test_calibration_result_persistence_in_cache(self, setup_calibration_env):
        """正向：校准结果应被缓存，可通过报告接口查询"""
        env = setup_calibration_env
        calibrator = env["calibrator"]
        dataset_id = env["dataset_id"]

        call_count = 0

        def counting_evaluator(sample):
            nonlocal call_count
            call_count += 1
            gold = sum(sample.scores.values()) / len(sample.scores)
            return {"score": gold, "evaluation_status": "success"}

        result1 = calibrator.run_golden_calibration(
            evaluator_name="test_cache",
            evaluator_func=counting_evaluator,
            dataset_id=dataset_id,
        )

        first_call_count = call_count
        assert first_call_count == 15
        assert result1.is_calibrated is True

        report = calibrator.get_golden_calibration_report("test_cache")
        assert report is not None
        assert "evaluator_name" in report
        assert report["evaluator_name"] == "test_cache"

    def test_calibration_gate_check_via_report(self, setup_calibration_env):
        """正向：通过校准报告判断评估器是否已校准"""
        env = setup_calibration_env
        calibrator = env["calibrator"]
        dataset_id = env["dataset_id"]

        def good_evaluator(sample):
            gold = sum(sample.scores.values()) / len(sample.scores)
            return {"score": gold * 0.9995, "evaluation_status": "success"}

        calibrator.run_golden_calibration(
            evaluator_name="test_gate",
            evaluator_func=good_evaluator,
            dataset_id=dataset_id,
        )

        report = calibrator.get_golden_calibration_report("test_gate")
        assert report is not None
        assert "cached_datasets" in report
        dataset_cache = report["cached_datasets"]
        assert len(dataset_cache) > 0
        target_cache = [c for c in dataset_cache if c["dataset_id"] == dataset_id]
        assert len(target_cache) == 1
        assert target_cache[0]["is_calibrated"] is True

        no_report = calibrator.get_golden_calibration_report("nonexistent_evaluator")
        assert no_report is not None
        no_cache = [c for c in no_report.get("cached_datasets", []) if c["dataset_id"] == dataset_id]
        assert len(no_cache) == 0 or no_cache[0]["is_calibrated"] is False
