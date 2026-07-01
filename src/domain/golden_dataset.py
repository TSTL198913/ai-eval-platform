import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4


@dataclass
class GoldenSample:
    id: str
    user_input: str
    actual_output: str
    expected_output: str | None = None
    dimensions: list[str] = field(default_factory=lambda: ["correctness"])
    scores: dict[str, float] = field(default_factory=dict)
    human_corrected: bool = False
    corrected_by: str | None = None
    corrected_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return dict(vars(self).items())

    def to_few_shot_example(self) -> str:
        scores_str = ", ".join([f"{k}: {v}/100" for k, v in self.scores.items()])
        expected_section = f"\n期望输出: {self.expected_output}" if self.expected_output else ""
        return f"示例开始\n用户问题: {self.user_input}\n模型输出: {self.actual_output}{expected_section}\n评分结果: {scores_str}\n示例结束\n"


@dataclass
class GoldenDataset:
    id: str
    name: str
    description: str
    category: str
    samples: list[GoldenSample] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def corrected_count(self) -> int:
        return sum(1 for s in self.samples if s.human_corrected)


class GoldenDatasetManager:
    def __init__(self, data_dir: str = "data/golden_datasets"):
        self._datasets: dict[str, GoldenDataset] = {}
        self._sample_index: dict[str, GoldenSample] = {}
        self._data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)

    def create_dataset(
        self, name: str, description: str = "", category: str = "general"
    ) -> GoldenDataset:
        dataset_id = str(uuid4())[:8]
        dataset = GoldenDataset(
            id=dataset_id, name=name, description=description, category=category
        )
        self._datasets[dataset_id] = dataset
        return dataset

    def add_sample(self, dataset_id: str, sample_data: dict[str, Any]) -> GoldenSample | None:
        dataset = self._datasets.get(dataset_id)
        if not dataset:
            return None
        sample = GoldenSample(
            id=sample_data.get("id", str(uuid4())[:8]),
            user_input=sample_data["user_input"],
            actual_output=sample_data["actual_output"],
            expected_output=sample_data.get("expected_output"),
            dimensions=sample_data.get("dimensions", ["correctness"]),
            scores=sample_data.get("scores", {}),
        )
        dataset.samples.append(sample)
        self._sample_index[sample.id] = sample
        return sample

    def add_evaluation_result(self, dataset_id: str, request: dict, response: dict) -> GoldenSample | None:
        """从评估结果创建样本"""
        sample_data = {
            "user_input": request.get("user_input", request.get("input", "")),
            "actual_output": request.get("actual_output", request.get("output", "")),
            "expected_output": request.get("expected_output"),
            "dimensions": response.get("dimensions_evaluated", ["correctness"]),
            "scores": {
                "overall": response.get("score", 0.0),
            },
            "metadata": {
                "evaluator_type": response.get("evaluator_type"),
                "evaluation_status": response.get("evaluation_status"),
                "confidence": response.get("confidence"),
            },
        }
        return self.add_sample(dataset_id, sample_data)

    def correct_sample(
        self, sample_id: str, corrected_scores: dict[str, float], corrected_by: str
    ) -> GoldenSample | None:
        """校正样本评分 - 合并而非覆盖，避免数据丢失"""
        sample = self._sample_index.get(sample_id)
        if not sample:
            return None
        sample.scores.update(corrected_scores)
        sample.human_corrected = True
        sample.corrected_by = corrected_by
        sample.corrected_at = datetime.utcnow()
        sample.updated_at = datetime.utcnow()
        return sample

    def get_samples(self, dataset_id: str, limit: int = 100, offset: int = 0) -> list[GoldenSample]:
        """获取样本列表"""
        dataset = self._datasets.get(dataset_id)
        if not dataset:
            return []
        return dataset.samples[offset : offset + limit]

    def get_high_conflict_samples(
        self, dataset_id: str, inconsistency_threshold: float = 0.3, limit: int = 20
    ) -> list[GoldenSample]:
        """获取高冲突样本（多评审员不一致度 > 阈值）"""
        dataset = self._datasets.get(dataset_id)
        if not dataset:
            return []

        conflict_samples = []
        for sample in dataset.samples:
            if len(sample.scores) >= 2:
                scores = list(sample.scores.values())
                score_range = max(scores) - min(scores)
                normalized_range = score_range / max(max(scores), 1.0)
                if normalized_range > inconsistency_threshold:
                    conflict_samples.append((sample, normalized_range))

        conflict_samples.sort(key=lambda x: x[1], reverse=True)
        return [s[0] for s in conflict_samples[:limit]]

    def get_sample_statistics(self, dataset_id: str) -> dict[str, Any]:
        """获取数据集统计信息"""
        dataset = self._datasets.get(dataset_id)
        if not dataset:
            return {}

        total_samples = len(dataset.samples)
        corrected_samples = sum(1 for s in dataset.samples if s.human_corrected)
        avg_score = 0.0
        score_count = 0
        for sample in dataset.samples:
            if sample.scores:
                avg_score += sum(sample.scores.values()) / len(sample.scores)
                score_count += 1

        return {
            "total_samples": total_samples,
            "corrected_samples": corrected_samples,
            "corrected_ratio": corrected_samples / total_samples if total_samples > 0 else 0,
            "avg_score": avg_score / score_count if score_count > 0 else 0,
            "conflict_samples": len(self.get_high_conflict_samples(dataset_id)),
        }

    def get_few_shot_examples(self, dataset_id: str, limit: int = 5) -> list[str]:
        dataset = self._datasets.get(dataset_id)
        if not dataset:
            return []
        candidates = sorted(
            [s for s in dataset.samples if s.human_corrected],
            key=lambda x: x.updated_at,
            reverse=True,
        )[:limit]
        return [s.to_few_shot_example() for s in candidates]

    def get_dataset(self, dataset_id: str) -> GoldenDataset | None:
        return self._datasets.get(dataset_id)

    def list_datasets(self) -> list[GoldenDataset]:
        return list(self._datasets.values())


golden_dataset_manager = GoldenDatasetManager()
