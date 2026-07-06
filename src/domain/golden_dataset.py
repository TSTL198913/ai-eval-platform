import json
import os
from dataclasses import dataclass
from dataclasses import field
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

    @property
    def input_data(self) -> dict[str, Any]:
        """评估输入数据：将 GoldenSample 字段映射为评估器 payload 格式

        校准引擎和自修复模块通过 sample.input_data 获取评估请求数据，
        该属性统一字段映射，避免各模块自行构造时的不一致。
        """
        payload: dict[str, Any] = {
            "user_input": self.user_input,
            "input": self.user_input,
            "actual_output": self.actual_output,
        }
        if self.expected_output is not None:
            payload["expected_output"] = self.expected_output
        if self.dimensions:
            payload["dimensions"] = list(self.dimensions)
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        if self.scores and "golden_score" not in self.metadata:
            overall_score = sum(self.scores.values()) / len(self.scores)
            if "metadata" not in payload:
                payload["metadata"] = {}
            payload["metadata"]["golden_score"] = overall_score
        return payload

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
        
        metadata = sample_data.get("metadata", {})
        if "golden_score" not in metadata and sample_data.get("scores"):
            overall_score = sample_data["scores"].get("overall")
            if overall_score is not None:
                metadata["golden_score"] = overall_score
        
        sample = GoldenSample(
            id=sample_data.get("id", str(uuid4())[:8]),
            user_input=sample_data["user_input"],
            actual_output=sample_data["actual_output"],
            expected_output=sample_data.get("expected_output"),
            dimensions=sample_data.get("dimensions", ["correctness"]),
            scores=sample_data.get("scores", {}),
            metadata=metadata,
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

    def get_few_shot_examples(
        self,
        dataset_id: str,
        limit: int = 5,
        dimensions: list[str] | None = None,
    ) -> list[str]:
        """获取 few-shot 示例，支持按维度过滤

        Args:
            dataset_id: 黄金数据集ID
            limit: 最大返回数量
            dimensions: 可选的维度过滤（如 ["correctness", "relevance"]），
                        仅返回包含这些维度标注的样本
        """
        dataset = self._datasets.get(dataset_id)
        if not dataset:
            return []

        candidates = [s for s in dataset.samples if s.human_corrected]

        if dimensions:
            filtered = []
            for sample in candidates:
                if sample.dimensions and any(d in sample.dimensions for d in dimensions):
                    filtered.append(sample)
            candidates = filtered

        candidates = sorted(candidates, key=lambda x: x.updated_at, reverse=True)[:limit]
        return [s.to_few_shot_example() for s in candidates]

    def get_dataset(self, dataset_id: str) -> GoldenDataset | None:
        return self._datasets.get(dataset_id)

    def get_dataset_by_category(self, category: str) -> GoldenDataset | None:
        """按类别获取数据集"""
        for dataset in self._datasets.values():
            if dataset.category == category:
                return dataset
        return None

    def delete_dataset(self, dataset_id: str) -> bool:
        """删除数据集"""
        if dataset_id in self._datasets:
            dataset = self._datasets[dataset_id]
            for sample in dataset.samples:
                self._sample_index.pop(sample.id, None)
            del self._datasets[dataset_id]
            return True
        return False

    def list_datasets(self) -> list[GoldenDataset]:
        return list(self._datasets.values())

    def save_datasets(self):
        """保存所有数据集到文件"""
        data = []
        for dataset in self._datasets.values():
            dataset_dict = {
                "id": dataset.id,
                "name": dataset.name,
                "description": dataset.description,
                "category": dataset.category,
                "created_at": dataset.created_at.isoformat(),
                "updated_at": dataset.updated_at.isoformat(),
                "samples": [],
            }
            for sample in dataset.samples:
                sample_dict = {
                    "id": sample.id,
                    "user_input": sample.user_input,
                    "actual_output": sample.actual_output,
                    "expected_output": sample.expected_output,
                    "dimensions": sample.dimensions,
                    "scores": sample.scores,
                    "human_corrected": sample.human_corrected,
                    "corrected_by": sample.corrected_by,
                    "corrected_at": sample.corrected_at.isoformat() if sample.corrected_at else None,
                    "metadata": sample.metadata,
                    "created_at": sample.created_at.isoformat(),
                    "updated_at": sample.updated_at.isoformat(),
                }
                dataset_dict["samples"].append(sample_dict)
            data.append(dataset_dict)

        for dataset in self._datasets.values():
            dataset_dict = {
                "id": dataset.id,
                "name": dataset.name,
                "description": dataset.description,
                "category": dataset.category,
                "created_at": dataset.created_at.isoformat(),
                "updated_at": dataset.updated_at.isoformat(),
                "samples": [],
            }
            for sample in dataset.samples:
                sample_dict = {
                    "id": sample.id,
                    "user_input": sample.user_input,
                    "actual_output": sample.actual_output,
                    "expected_output": sample.expected_output,
                    "dimensions": sample.dimensions,
                    "scores": sample.scores,
                    "human_corrected": sample.human_corrected,
                    "corrected_by": sample.corrected_by,
                    "corrected_at": sample.corrected_at.isoformat() if sample.corrected_at else None,
                    "metadata": sample.metadata,
                    "created_at": sample.created_at.isoformat(),
                    "updated_at": sample.updated_at.isoformat(),
                }
                dataset_dict["samples"].append(sample_dict)
            
            filename = f"{dataset.id}.json"
            filepath = os.path.join(self._data_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(dataset_dict, f, ensure_ascii=False, indent=2)

        index_file = os.path.join(self._data_dir, "_index.json")
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "datasets": [{"id": d.id, "name": d.name, "category": d.category} for d in self._datasets.values()]
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

    def load_datasets(self):
        """从文件加载所有数据集"""
        self._datasets.clear()
        self._sample_index.clear()

        index_file = os.path.join(self._data_dir, "_index.json")
        if not os.path.exists(index_file):
            return

        with open(index_file, "r", encoding="utf-8") as f:
            index = json.load(f)

        for dataset_info in index.get("datasets", []):
            dataset_id = dataset_info["id"]
            filename = f"{dataset_id}.json"
            filepath = os.path.join(self._data_dir, filename)
            if not os.path.exists(filepath):
                continue

            with open(filepath, "r", encoding="utf-8") as f:
                dataset_dict = json.load(f)

            dataset = GoldenDataset(
                id=dataset_dict["id"],
                name=dataset_dict["name"],
                description=dataset_dict.get("description", ""),
                category=dataset_dict.get("category", "general"),
                created_at=datetime.fromisoformat(dataset_dict.get("created_at", datetime.utcnow().isoformat())),
                updated_at=datetime.fromisoformat(dataset_dict.get("updated_at", datetime.utcnow().isoformat())),
                samples=[],
            )

            for sample_dict in dataset_dict.get("samples", []):
                sample = GoldenSample(
                    id=sample_dict["id"],
                    user_input=sample_dict["user_input"],
                    actual_output=sample_dict["actual_output"],
                    expected_output=sample_dict.get("expected_output"),
                    dimensions=sample_dict.get("dimensions", ["correctness"]),
                    scores=sample_dict.get("scores", {}),
                    human_corrected=sample_dict.get("human_corrected", False),
                    corrected_by=sample_dict.get("corrected_by"),
                    corrected_at=datetime.fromisoformat(sample_dict["corrected_at"]) if sample_dict.get("corrected_at") else None,
                    metadata=sample_dict.get("metadata", {}),
                    created_at=datetime.fromisoformat(sample_dict.get("created_at", datetime.utcnow().isoformat())),
                    updated_at=datetime.fromisoformat(sample_dict.get("updated_at", datetime.utcnow().isoformat())),
                )
                dataset.samples.append(sample)
                self._sample_index[sample.id] = sample

            self._datasets[dataset.id] = dataset


golden_dataset_manager = GoldenDatasetManager()
golden_dataset_manager.load_datasets()
