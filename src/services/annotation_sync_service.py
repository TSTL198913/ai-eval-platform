"""
标注同步服务（Annotation Sync Service）

将人工标注结果自动同步到黄金数据集，闭合 PDCA 循环：
- 标注任务完成 → 结果转换为 GoldenSample → 添加到黄金数据集
- 多标注员结果聚合后同步
- 同步后发布 CALIBRATION_NEEDED 事件，触发重新校准

解决 BUG-016: 人工标注结果未自动同步到黄金数据集
"""

import logging
from datetime import datetime
from typing import Any

from src.domain.golden_dataset import GoldenSample, golden_dataset_manager
from src.infra.event_bus import EventBus, Event, EventType

logger = logging.getLogger(__name__)


class AnnotationSyncService:
    """标注结果 → 黄金数据集同步服务"""

    def __init__(self, dataset_manager=None):
        self._dataset_manager = dataset_manager or golden_dataset_manager
        self._event_bus = EventBus()

    def sync_completed_annotation(
        self,
        annotation_data: dict[str, Any],
        dataset_id: str,
    ) -> GoldenSample | None:
        """将已完成的标注结果同步到黄金数据集

        Args:
            annotation_data: 标注数据，包含 question, actual_output, expected_output,
                             score, dimensions, annotator_name, status 等
            dataset_id: 目标黄金数据集ID

        Returns:
            创建的 GoldenSample，若不同步则返回 None

        Raises:
            ValueError: 标注分数超出 [0, 1] 范围
        """
        status = annotation_data.get("status", "completed")
        if status not in ("completed", "COMPLETED"):
            logger.debug(f"标注任务状态为 {status}，跳过同步")
            return None

        score = annotation_data.get("score", 0)
        if not (0 <= score <= 1):
            raise ValueError(f"分数 {score} 超出范围 [0, 1]")

        dimensions = annotation_data.get("dimensions", {})
        for dim_name, dim_score in dimensions.items():
            if not (0 <= dim_score <= 1):
                raise ValueError(f"维度 {dim_name} 分数 {dim_score} 超出范围 [0, 1]")

        evaluator_type = annotation_data.get("evaluator_type", "general")
        annotator_name = annotation_data.get("annotator_name", "unknown")

        scores: dict[str, float] = {}
        if dimensions:
            for dim_name, dim_score in dimensions.items():
                scores[dim_name] = float(dim_score)
        else:
            scores["overall"] = float(score)

        metadata = {
            "annotator_id": annotation_data.get("annotator_id"),
            "annotator_name": annotator_name,
            "evaluator_type": evaluator_type,
            "annotation_score": float(score),
            "label": annotation_data.get("label"),
            "comment": annotation_data.get("comment"),
            "synced_at": datetime.utcnow().isoformat(),
        }
        task_metadata = annotation_data.get("metadata", {})
        if task_metadata:
            metadata["task_metadata"] = task_metadata

        sample_data = {
            "user_input": annotation_data.get("question", annotation_data.get("user_input", "")),
            "actual_output": annotation_data.get("actual_output", ""),
            "expected_output": annotation_data.get("expected_output"),
            "dimensions": list(dimensions.keys()) if dimensions else ["correctness"],
            "scores": scores,
            "metadata": metadata,
        }

        sample = self._dataset_manager.add_sample(dataset_id, sample_data)
        if sample is None:
            logger.error(f"同步失败: 数据集 {dataset_id} 不存在")
            return None

        sample.human_corrected = True
        sample.corrected_by = annotator_name
        sample.corrected_at = datetime.utcnow()
        sample.updated_at = datetime.utcnow()

        logger.info(
            f"标注结果已同步到黄金数据集 | dataset={dataset_id} | "
            f"sample={sample.id} | annotator={annotator_name} | evaluator={evaluator_type}"
        )

        self._publish_calibration_needed(evaluator_type, dataset_id, sample.id)

        return sample

    def sync_multi_annotator_results(
        self,
        annotations: list[dict[str, Any]],
        dataset_id: str,
    ) -> GoldenSample | None:
        """多标注员结果聚合后同步

        将多个标注员的结果聚合（取平均分），然后作为一个 GoldenSample 同步。

        Args:
            annotations: 标注结果列表，每个元素包含 score, dimensions, annotator_name 等
            dataset_id: 目标黄金数据集ID

        Returns:
            创建的 GoldenSample

        Raises:
            ValueError: 标注分数超出范围 或 标注列表为空
        """
        if not annotations:
            raise ValueError("标注列表不能为空")

        for ann in annotations:
            score = ann.get("score", 0)
            if not (0 <= score <= 1):
                raise ValueError(f"标注分数 {score} 超出范围 [0, 1]")

        base = annotations[0]
        all_dimensions: dict[str, list[float]] = {}
        all_scores: list[float] = []

        for ann in annotations:
            all_scores.append(float(ann.get("score", 0)))
            dim_scores = ann.get("dimensions", {})
            for dim_name, dim_val in dim_scores.items():
                if dim_name not in all_dimensions:
                    all_dimensions[dim_name] = []
                all_dimensions[dim_name].append(float(dim_val))

        avg_scores: dict[str, float] = {}
        for dim_name, vals in all_dimensions.items():
            avg_scores[dim_name] = sum(vals) / len(vals)
        if not avg_scores:
            avg_scores["overall"] = sum(all_scores) / len(all_scores)

        annotator_names = [a.get("annotator_name", "unknown") for a in annotations]
        aggregated_data = {
            **base,
            "score": sum(all_scores) / len(all_scores),
            "dimensions": avg_scores,
            "annotator_name": ", ".join(annotator_names),
            "metadata": {
                **base.get("metadata", {}),
                "aggregated_from": len(annotations),
                "annotators": annotator_names,
            },
        }

        return self.sync_completed_annotation(aggregated_data, dataset_id)

    def _publish_calibration_needed(
        self, evaluator_name: str, dataset_id: str, sample_id: str
    ) -> None:
        """发布校准需求事件"""
        try:
            self._event_bus.publish(
                EventType.CALIBRATION_NEEDED,
                evaluator_name=evaluator_name,
                reason="new_golden_sample_added",
                dataset_id=dataset_id,
                sample_id=sample_id,
                priority="normal",
                source="annotation_sync_service",
            )
            logger.debug(f"已发布 CALIBRATION_NEEDED 事件 | evaluator={evaluator_name}")
        except Exception as e:
            logger.warning(f"发布 CALIBRATION_NEEDED 事件失败: {e}")
