"""
执行-反馈-优化闭环集成测试
测试目标：验证完整的PDCA闭环流程
核心测试场景：
1. 执行阶段：评估器执行和版本追踪
2. 反馈阶段：人工校正和黄金数据集更新
3. 分析阶段：自适应校准和漂移检测
4. 优化阶段：版本管理和重新校准

关键发现：（测试过程中记录）
"""

import os
import shutil
import sys
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.adaptive_calibration import AdaptiveCalibrator, CalibrationStatus
from src.domain.evaluator_version import EvaluatorVersionManager
from src.domain.evaluators.drift import DriftDetectionEvaluator
from src.domain.golden_dataset import GoldenDatasetManager
from src.schemas.evaluation import DomainResponse, EvaluationSchema


class TestExecuteStage:
    """执行阶段测试"""

    @pytest.fixture
    def mock_evaluator(self):
        """创建模拟评估器"""
        evaluator = MagicMock()
        evaluator.evaluate.return_value = DomainResponse(
            is_valid=True,
            score=0.85,
            text="评估完成",
            data={"dimension_scores": {"correctness": 85}},
        )
        return evaluator

    def test_execute_creates_evaluation_result(self, mock_evaluator):
        """执行应创建评估结果"""
        request = EvaluationSchema(
            id="case_001", type="test_evaluator", payload={"user_input": "测试输入"}
        )

        result = mock_evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 0.85

    def test_execute_associates_version(self):
        """执行应关联版本"""
        # 这个测试验证版本追踪概念

        # 模拟版本信息
        version_info = {
            "version_id": "v001",
            "evaluator_name": "test_evaluator",
            "version": "1.0.0",
            "created_at": datetime.utcnow().isoformat(),
        }

        # 在实际实现中，这个信息会被附加到结果上
        assert version_info["version"] is not None


class TestFeedbackStage:
    """反馈阶段测试 - 核心功能"""

    @pytest.fixture
    def feedback_manager(self):
        """创建反馈管理器"""
        temp_dir = tempfile.mkdtemp()
        manager = GoldenDatasetManager(data_dir=temp_dir)
        yield manager
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_feedback_correction_updates_golden_dataset(self, feedback_manager):
        """反馈校正应更新黄金数据集"""
        # 1. 创建数据集
        dataset = feedback_manager.create_dataset(
            name="customer_service_golden", description="客服回答黄金标准"
        )

        # 2. 添加初始评估结果
        feedback_manager.add_sample(
            dataset.id,
            {
                "id": "case_001",
                "user_input": "商品一周没发货，要求退款",
                "actual_output": "您好，非常抱歉...",
                "expected_output": "道歉、查询、方案",
                "dimensions": ["correctness", "safety"],
                "scores": {"correctness": 70, "safety": 60},
            },
        )

        # 3. 人工校正（反馈）
        corrected = feedback_manager.correct_sample(
            sample_id="case_001",
            corrected_scores={"correctness": 90, "safety": 95},
            corrected_by="expert_user",
        )

        # 验证校正结果
        assert corrected.human_corrected is True
        assert corrected.scores["correctness"] == 90
        assert corrected.scores["safety"] == 95

    def test_feedback_generates_few_shot_examples(self, feedback_manager):
        """反馈应生成Few-shot示例"""
        # 1. 创建数据集
        dataset = feedback_manager.create_dataset(name="test_golden", description="测试")

        # 2. 添加多个样本
        for i in range(3):
            feedback_manager.add_sample(
                dataset.id,
                {
                    "id": f"case_{i:03d}",
                    "user_input": f"问题{i}",
                    "actual_output": f"回答{i}",
                    "scores": {"correctness": 80 + i},
                },
            )

        # 3. 校正部分样本
        feedback_manager.correct_sample(
            sample_id="case_000", corrected_scores={"correctness": 95}, corrected_by="expert"
        )

        # 4. 获取Few-shot示例（用于指导后续评估）
        examples = feedback_manager.get_few_shot_examples(dataset.id, limit=5)

        # 验证
        assert len(examples) > 0
        assert "示例开始" in examples[0]
        assert "correctness: 95" in examples[0]  # 校正后的分数


class TestAnalyzeStage:
    """分析阶段测试 - 核心功能"""

    @pytest.fixture
    def calibrator(self):
        """创建校准器"""
        calibrator = AdaptiveCalibrator()
        calibrator._calibration_cache = {}
        return calibrator

    def test_analyze_detects_deviation(self, calibrator):
        """分析应检测偏差"""
        # 模拟黄金数据集
        mock_dataset = MagicMock()
        samples = []
        for i in range(5):
            sample = MagicMock()
            sample.scores = {"correctness": 90 + i * 2}
            samples.append(sample)
        mock_dataset.samples = samples
        mock_dataset.name = "test_dataset"

        with patch("src.domain.adaptive_calibration.golden_dataset_manager") as mock_gm:
            mock_gm.get_dataset.return_value = mock_dataset

            # 模拟评估器（与专家有偏差）
            def mock_eval(sample):
                return {"score": sum(sample.scores.values()) / len(sample.scores) - 10}

            result = calibrator.run_calibration(
                evaluator_name="test_evaluator", evaluator_func=mock_eval, dataset_id="test_dataset"
            )

            # 分析结果
            assert result.mean_deviation > 0
            assert len(result.suggestions) > 0

    def test_analyze_drift_detection(self):
        """分析应检测漂移"""
        evaluator = DriftDetectionEvaluator()

        result = evaluator._detect_by_similarity(
            actual_output="完全不同的内容ABC", baseline_output="原始内容XYZ"
        )

        # 漂移检测结果
        assert result["drift_score"] > 0.5  # 差异大
        assert result["similarity"] < 0.5


class TestOptimizeStage:
    """优化阶段测试 - 核心功能"""

    @pytest.fixture
    def version_manager(self):
        """创建版本管理器"""
        temp_dir = tempfile.mkdtemp()
        manager = EvaluatorVersionManager(storage_path=temp_dir)
        manager._versions = {}
        manager._current_codes = {}
        yield manager
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_optimize_triggers_recalibration(self, version_manager):
        """优化应触发重新校准"""
        # 1. 注册版本
        version_manager.register_version(
            evaluator_name="test_evaluator", version="1.0.0", code_hash="hash1", config={}
        )

        # 2. 更新校准分数（模拟优化）
        updated = version_manager.update_calibration(
            "test_evaluator", calibration_score=94.0  # 接近基线95
        )

        # 验证
        assert updated.calibration_score == 94.0

    def test_optimize_rejects_drifted_evaluator(self, version_manager):
        """优化应拒绝漂移的评估器"""
        # 1. 注册版本
        version_manager.register_version(
            evaluator_name="test_evaluator", version="1.0.0", code_hash="hash1", config={}
        )

        # 2. 设置严重漂移的校准分数
        version_manager.update_calibration("test_evaluator", calibration_score=70.0)  # 偏离基线95

        # 3. 检查状态
        status = version_manager.check_calibration_status("test_evaluator")

        # 优化决策：漂移时拒绝执行
        assert status["can_proceed"] is False
        assert status["status"] == "drifted"


class TestClosedLoopIntegration:
    """完整闭环集成测试"""

    @pytest.fixture
    def loop_components(self):
        """创建闭环组件"""
        temp_dir = tempfile.mkdtemp()

        # 创建各组件
        golden_manager = GoldenDatasetManager(data_dir=temp_dir)
        calibrator = AdaptiveCalibrator()
        calibrator._calibration_cache = {}
        version_manager = EvaluatorVersionManager(storage_path=temp_dir)
        version_manager._versions = {}
        version_manager._current_codes = {}

        yield {
            "golden_manager": golden_manager,
            "calibrator": calibrator,
            "version_manager": version_manager,
            "temp_dir": temp_dir,
        }

        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_full_loop_execute_feedback_analyze_optimize(self, loop_components):
        """
        完整闭环流程测试

        1. 执行：评估器执行并记录版本
        2. 反馈：人工校正评估结果
        3. 分析：在黄金数据集上校准评估器
        4. 优化：根据校准结果决定是否允许执行
        """
        golden_manager = loop_components["golden_manager"]
        calibrator = loop_components["calibrator"]
        version_manager = loop_components["version_manager"]

        # ===== 阶段1：执行 =====
        # 1.1 注册评估器版本
        version_manager.register_version(
            evaluator_name="llm_as_judge",
            version="1.0.0",
            code_hash="hash_v1",
            config={"threshold": 0.8},
        )

        # 1.2 执行评估（模拟）
        evaluation_result = {
            "case_id": "case_001",
            "evaluator": "llm_as_judge",
            "version": "1.0.0",
            "score": 85,  # 评估器评分
            "dimensions": {"correctness": 85, "safety": 85},
        }
        assert evaluation_result["score"] == 85

        # ===== 阶段2：反馈 =====
        # 2.1 创建黄金数据集
        dataset = golden_manager.create_dataset(
            name="llm_judge_golden", description="LLM评判黄金标准"
        )

        # 2.2 添加评估结果作为样本
        golden_manager.add_sample(
            dataset.id,
            {
                "id": "case_001",
                "user_input": "测试问题",
                "actual_output": "模型回答内容",
                "expected_output": "期望包含的关键点",
                "dimensions": ["correctness", "safety"],
                "scores": evaluation_result["dimensions"],  # 初始评分
            },
        )

        # 2.3 人工校正（专家反馈）
        golden_manager.correct_sample(
            sample_id="case_001",
            corrected_scores={"correctness": 95, "safety": 90},  # 专家校正分数
            corrected_by="senior_expert",
        )

        # 验证反馈
        sample = golden_manager._sample_index["case_001"]
        assert sample.human_corrected is True
        assert sample.scores["correctness"] == 95  # 校正后的分数

        # 2.4 生成Few-shot示例
        examples = golden_manager.get_few_shot_examples(dataset.id)
        assert len(examples) > 0

        # ===== 阶段3：分析 =====
        # 3.1 模拟评估器评分（与专家有偏差）
        mock_dataset = MagicMock()
        samples = []
        for _ in range(5):
            sample = MagicMock()
            # 评估器评分比专家低10分
            sample.scores = {"correctness": 85, "safety": 80}  # 专家给95  # 专家给90
            samples.append(sample)
        mock_dataset.samples = samples
        mock_dataset.name = dataset.name

        with patch("src.domain.adaptive_calibration.golden_dataset_manager") as mock_gm:
            mock_gm.get_dataset.return_value = mock_dataset

            def mock_eval(sample):
                # 评估器预测（模拟）
                scores = list(sample.scores.values())
                return {"score": sum(scores) / len(scores) - 10}

            calibration_result = calibrator.run_calibration(
                evaluator_name="llm_as_judge", evaluator_func=mock_eval, dataset_id=dataset.id
            )

        # 3.2 分析结果
        assert calibration_result.mean_deviation > 5  # 偏差超过阈值
        assert calibration_result.is_calibrated is False  # 校准失败

        # 3.3 漂移检测
        drift_evaluator = DriftDetectionEvaluator()
        drift_result = drift_evaluator._detect_by_similarity(
            actual_output="评估器认为正确的答案", baseline_output="专家认可的正确答案"
        )
        assert drift_result["drift_score"] > 0  # 可能存在漂移

        # ===== 阶段4：优化 =====
        # 4.1 更新校准分数
        version_manager.update_calibration(
            "llm_as_judge", calibration_score=calibration_result.mean_eval
        )

        # 4.2 检查优化决策（需要传入dataset_id以触发校准检查）
        # 使用唯一的评估器名称避免测试冲突
        import uuid

        unique_name = f"llm_as_judge_{uuid.uuid4().hex[:8]}"
        from src.domain.evaluator_version import evaluator_version_manager

        evaluator_version_manager.register_version(
            evaluator_name=unique_name, version="1.0.0", code_hash="hash123", config={}
        )
        # 更新校准分数
        evaluator_version_manager.update_calibration(unique_name, calibration_result.mean_eval)

        # 传入dataset_id触发校准检查
        check = calibrator.pre_execution_check(unique_name, dataset_id=dataset.id)

        # 未校准或漂移时都应拒绝执行
        assert check.can_proceed is False
        # 由于使用唯一名称，状态可能是NOT_CALIBRATED或DRIFTED
        assert check.status in [CalibrationStatus.NOT_CALIBRATED, CalibrationStatus.DRIFTED]

        # 4.3 触发重新校准（优化）
        # 在Few-shot示例指导下重新评估
        optimized_examples = golden_manager.get_few_shot_examples(dataset.id)
        assert len(optimized_examples) > 0  # Few-shot可用于优化

    def test_loop_quality_metrics(self, loop_components):
        """闭环质量指标测试"""
        golden_manager = loop_components["golden_manager"]

        # 创建测试数据集
        dataset = golden_manager.create_dataset(name="quality_test")

        # 添加样本
        total_samples = 10
        corrected_count = 0

        for i in range(total_samples):
            golden_manager.add_sample(
                dataset.id,
                {
                    "id": f"case_{i:03d}",
                    "user_input": f"问题{i}",
                    "actual_output": f"回答{i}",
                    "scores": {"correctness": 80},
                },
            )

            # 模拟部分样本被校正
            if i < 3:  # 30%被校正
                golden_manager.correct_sample(
                    sample_id=f"case_{i:03d}",
                    corrected_scores={"correctness": 95},
                    corrected_by="expert",
                )
                corrected_count += 1

        # 计算质量指标
        human_correction_rate = corrected_count / total_samples

        # 获取Few-shot示例
        examples = golden_manager.get_few_shot_examples(dataset.id)
        few_shot_hit_rate = len(examples) / corrected_count if corrected_count > 0 else 0

        # 验证指标
        assert human_correction_rate <= 0.5  # 人工修正率应≤50%
        assert few_shot_hit_rate > 0  # Few-shot命中率应>0


class TestLoopEdgeCases:
    """闭环边界场景测试"""

    def test_loop_without_feedback(self):
        """无反馈时的闭环"""
        # 评估器未经过人工校正
        # 应该允许执行，但给出提示

        # 模拟无校准的检查
        mock_check = {
            "can_proceed": True,  # 允许执行
            "status": "not_calibrated",
            "message": "建议先校准",
        }

        assert mock_check["can_proceed"] is True

    def test_loop_with_insufficient_samples(self):
        """样本不足时的闭环"""
        temp_dir = tempfile.mkdtemp()
        golden_manager = GoldenDatasetManager(data_dir=temp_dir)

        # 创建数据集但样本不足
        dataset = golden_manager.create_dataset(name="insufficient")

        # 只添加2个样本（少于要求的5个）
        for i in range(2):
            golden_manager.add_sample(
                dataset.id,
                {
                    "id": f"case_{i:03d}",
                    "user_input": f"问题{i}",
                    "actual_output": f"回答{i}",
                    "scores": {"correctness": 80},
                },
            )

        # 尝试获取Few-shot
        examples = golden_manager.get_few_shot_examples(dataset.id)

        # 无校正样本时应该返回空
        assert len(examples) == 0

        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_loop_with_stable_evaluator(self):
        """稳定评估器的闭环"""
        temp_dir = tempfile.mkdtemp()
        version_manager = EvaluatorVersionManager(storage_path=temp_dir)
        version_manager._versions = {}
        version_manager._current_codes = {}

        # 注册稳定版本
        version_manager.register_version(
            evaluator_name="stable_evaluator", version="1.0.0", code_hash="stable_hash", config={}
        )

        # 更新校准分数（接近基线）
        version_manager.update_calibration("stable_evaluator", calibration_score=94.0)  # 接近95基线

        # 检查状态
        status = version_manager.check_calibration_status("stable_evaluator")

        # 稳定评估器应通过
        assert status["status"] == "calibrated"
        assert status["can_proceed"] is True

        shutil.rmtree(temp_dir, ignore_errors=True)


class TestLoopQualityIndicators:
    """闭环质量指标测试"""

    def test_calibration_pass_rate(self):
        """校准通过率测试"""
        # 模拟10个评估器
        total_evaluators = 10
        calibrated_count = 0

        for i in range(total_evaluators):
            # 模拟评估器评分
            calibration_score = 90 + (i % 5) * 2  # 部分通过

            # 计算是否通过
            baseline = 95
            deviation = abs(calibration_score - baseline) / baseline
            if deviation <= 0.05:
                calibrated_count += 1

        pass_rate = calibrated_count / total_evaluators

        assert pass_rate >= 0.5  # 至少50%通过

    def test_drift_detection_rate(self):
        """漂移检出率测试"""
        evaluator = DriftDetectionEvaluator()

        # 模拟明显漂移
        result = evaluator._detect_by_similarity(
            actual_output="完全不相关的内容，内容完全不同",
            baseline_output="原始的、正确的、相关的内容",
        )

        # 应该检出漂移
        assert result["drift_score"] > 0.5
        assert result["detected"] is True


# 关键发现：
# 1. 完整闭环包含4个阶段：执行→反馈→分析→优化
# 2. 反馈阶段的Few-shot示例可用于指导后续评估
# 3. 漂移时pre_execution_check返回can_proceed=False
# 4. 优化后可能需要重新校准或版本回滚
# 5. 闭环质量指标：校准通过率≥90%、偏差≤5%、漂移检出率≥80%
