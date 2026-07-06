"""
回归测试：人工标注 → 黄金数据集自动更新链路
BUG-016: 人工标注结果未自动同步到黄金数据集 - 闭环断裂

测试场景覆盖：
1. 正向：标注任务完成 → 结果自动同步到黄金数据集
2. 正向：多标注员结果聚合后同步
3. 边界：标注任务未完成（in_progress）不应同步
4. 边界：标注被取消（cancelled）不应同步
5. 负向：无效标注结果不应污染黄金数据集
6. 集成：同步后黄金样本可被校准引擎使用
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime


class TestAnnotationGoldenLoop:
    """人工标注 → 黄金数据集闭环测试"""

    @pytest.fixture
    def mock_annotation_data(self):
        """模拟标注任务和结果数据"""
        return {
            "task_id": "task_001",
            "case_id": "case_001",
            "evaluator_type": "general",
            "question": "什么是机器学习？",
            "actual_output": "机器学习是AI的分支...",
            "expected_output": "机器学习是人工智能的一个分支，通过数据训练模型",
            "context": {"difficulty": "medium"},
            "metadata": {"source": "test_suite"},
            "annotator_id": "annotator_001",
            "annotator_name": "测试标注员",
            "score": 0.85,
            "label": "correct",
            "comment": "回答基本正确但不够详细",
            "dimensions": {"correctness": 0.9, "completeness": 0.8},
        }

    def test_completed_annotation_syncs_to_golden_dataset(self, mock_annotation_data):
        """正向：标注任务完成 → 结果自动同步到黄金数据集"""
        from src.domain.golden_dataset import golden_dataset_manager, GoldenDataset

        dataset = golden_dataset_manager.create_dataset(
            name="general_test",
            description="通用评估测试集",
            category="general",
        )

        from src.services.annotation_sync_service import AnnotationSyncService

        sync_service = AnnotationSyncService()
        result = sync_service.sync_completed_annotation(
            annotation_data=mock_annotation_data,
            dataset_id=dataset.id,
        )

        assert result is not None, "同步结果不应为None"
        assert result.user_input == mock_annotation_data["question"]
        assert result.actual_output == mock_annotation_data["actual_output"]
        assert result.expected_output == mock_annotation_data["expected_output"]
        assert result.human_corrected is True
        assert result.corrected_by == mock_annotation_data["annotator_name"]
        assert "correctness" in result.scores
        assert result.scores["correctness"] == pytest.approx(0.9)

    def test_in_progress_annotation_not_synced(self, mock_annotation_data):
        """边界：标注任务未完成（in_progress）不应同步"""
        from src.services.annotation_sync_service import AnnotationSyncService

        sync_service = AnnotationSyncService()
        mock_annotation_data["status"] = "in_progress"

        result = sync_service.sync_completed_annotation(
            annotation_data=mock_annotation_data,
            dataset_id="any_dataset",
        )

        assert result is None, "未完成的标注不应同步"

    def test_cancelled_annotation_not_synced(self, mock_annotation_data):
        """边界：标注被取消（cancelled）不应同步"""
        from src.services.annotation_sync_service import AnnotationSyncService

        sync_service = AnnotationSyncService()
        mock_annotation_data["status"] = "cancelled"

        result = sync_service.sync_completed_annotation(
            annotation_data=mock_annotation_data,
            dataset_id="any_dataset",
        )

        assert result is None, "已取消的标注不应同步"

    def test_multiple_annotators_aggregated_before_sync(self, mock_annotation_data):
        """正向：多标注员结果聚合后同步，分数取平均"""
        from src.services.annotation_sync_service import AnnotationSyncService
        from src.domain.golden_dataset import golden_dataset_manager, GoldenDataset

        dataset = golden_dataset_manager.create_dataset(
            name="multi_annotator_test",
            description="多标注员测试",
            category="general",
        )

        annotations = [
            {
                **mock_annotation_data,
                "annotator_id": "annotator_001",
                "annotator_name": "标注员A",
                "score": 0.8,
                "dimensions": {"correctness": 0.85, "completeness": 0.75},
            },
            {
                **mock_annotation_data,
                "annotator_id": "annotator_002",
                "annotator_name": "标注员B",
                "score": 0.9,
                "dimensions": {"correctness": 0.95, "completeness": 0.85},
            },
        ]

        sync_service = AnnotationSyncService()
        result = sync_service.sync_multi_annotator_results(
            annotations=annotations,
            dataset_id=dataset.id,
        )

        assert result is not None
        avg_correctness = (0.85 + 0.95) / 2
        assert result.scores["correctness"] == pytest.approx(avg_correctness)
        assert result.human_corrected is True

    def test_invalid_annotation_not_pollutes_golden_dataset(self, mock_annotation_data):
        """负向：无效标注结果（score<0或>1）不应污染黄金数据集"""
        from src.services.annotation_sync_service import AnnotationSyncService

        sync_service = AnnotationSyncService()
        invalid_data = {
            **mock_annotation_data,
            "score": 1.5,
            "dimensions": {"correctness": 1.5},
        }

        with pytest.raises(ValueError, match="分数.*超出范围"):
            sync_service.sync_completed_annotation(
                annotation_data=invalid_data,
                dataset_id="any_dataset",
            )

    def test_synced_sample_usable_by_calibrator(self, mock_annotation_data):
        """集成：同步后的黄金样本可被校准引擎使用（input_data 属性可访问）"""
        from src.services.annotation_sync_service import AnnotationSyncService
        from src.domain.golden_dataset import golden_dataset_manager, GoldenDataset

        dataset = golden_dataset_manager.create_dataset(
            name="calib_integration_test",
            description="校准集成测试",
            category="general",
        )

        sync_service = AnnotationSyncService()
        sample = sync_service.sync_completed_annotation(
            annotation_data=mock_annotation_data,
            dataset_id=dataset.id,
        )

        assert sample is not None
        assert hasattr(sample, "input_data"), "同步的样本必须有 input_data 属性"
        assert "actual_output" in sample.input_data
        assert "user_input" in sample.input_data
        assert "expected_output" in sample.input_data

    def test_sync_publishes_calibration_needed_event(self, mock_annotation_data):
        """正向：标注同步后应调用 publish 发布 CALIBRATION_NEEDED 事件"""
        from src.services.annotation_sync_service import AnnotationSyncService
        from src.domain.golden_dataset import golden_dataset_manager
        from src.infra.event_bus import EventType

        mock_bus = MagicMock()
        publish_calls = []
        mock_bus.publish = lambda event_type, **kwargs: publish_calls.append((event_type, kwargs))

        dataset = golden_dataset_manager.create_dataset(
            name="event_test",
            description="事件测试",
            category="general",
        )

        sync_service = AnnotationSyncService(dataset_manager=golden_dataset_manager)
        sync_service._event_bus = mock_bus

        sync_service.sync_completed_annotation(
            annotation_data=mock_annotation_data,
            dataset_id=dataset.id,
        )

        assert len(publish_calls) > 0, "应调用 publish 发布 CALIBRATION_NEEDED 事件"
        event_type, event_data = publish_calls[-1]
        assert event_type == EventType.CALIBRATION_NEEDED
        assert event_data.get("evaluator_name") == mock_annotation_data["evaluator_type"]
        assert event_data.get("reason") == "new_golden_sample_added"
