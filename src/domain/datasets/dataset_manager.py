from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4


@dataclass
class DatasetSample:
    id: str
    question: str
    choices: list[str] | None = None
    answer: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "choices": self.choices,
            "answer": self.answer,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class DatasetVersion:
    version_id: str
    dataset_id: str
    version_number: str
    samples: list[DatasetSample] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    description: str = ""
    is_active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "version_id": self.version_id,
            "dataset_id": self.dataset_id,
            "version_number": self.version_number,
            "sample_count": len(self.samples),
            "created_at": self.created_at.isoformat(),
            "description": self.description,
            "is_active": self.is_active,
        }


@dataclass
class Dataset:
    id: str
    name: str
    description: str
    category: str
    versions: list[DatasetVersion] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def latest_version(self) -> DatasetVersion | None:
        if not self.versions:
            return None
        return sorted(self.versions, key=lambda v: int(v.version_number[1:]), reverse=True)[0]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "version_count": len(self.versions),
            "latest_version": self.latest_version.to_dict() if self.latest_version else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class DatasetManager:
    def __init__(self):
        self._datasets: dict[str, Dataset] = {}
        self._sample_index: dict[str, DatasetSample] = {}

    def create_dataset(self, name: str, description: str, category: str) -> Dataset:
        dataset_id = str(uuid4())[:8]
        dataset = Dataset(
            id=dataset_id,
            name=name,
            description=description,
            category=category,
        )
        self._datasets[dataset_id] = dataset
        return dataset

    def get_dataset(self, dataset_id: str) -> Dataset | None:
        return self._datasets.get(dataset_id)

    def list_datasets(self) -> list[Dataset]:
        return list(self._datasets.values())

    def delete_dataset(self, dataset_id: str) -> bool:
        if dataset_id in self._datasets:
            del self._datasets[dataset_id]
            return True
        return False

    def create_version(
        self,
        dataset_id: str,
        samples: list[dict[str, Any]],
        description: str = "",
    ) -> DatasetVersion | None:
        dataset = self._datasets.get(dataset_id)
        if not dataset:
            return None

        version_number = f"v{len(dataset.versions) + 1}"
        version_id = str(uuid4())[:8]

        dataset_samples = []
        for sample_data in samples:
            sample = DatasetSample(
                id=sample_data.get("id", str(uuid4())[:8]),
                question=sample_data["question"],
                choices=sample_data.get("choices"),
                answer=sample_data.get("answer"),
                metadata=sample_data.get("metadata", {}),
            )
            dataset_samples.append(sample)
            self._sample_index[sample.id] = sample

        version = DatasetVersion(
            version_id=version_id,
            dataset_id=dataset_id,
            version_number=version_number,
            samples=dataset_samples,
            description=description,
        )

        for v in dataset.versions:
            v.is_active = False
        dataset.versions.append(version)
        dataset.updated_at = datetime.utcnow()

        return version

    def get_version(self, dataset_id: str, version_id: str) -> DatasetVersion | None:
        dataset = self._datasets.get(dataset_id)
        if not dataset:
            return None
        return next((v for v in dataset.versions if v.version_id == version_id), None)

    def get_active_version(self, dataset_id: str) -> DatasetVersion | None:
        dataset = self._datasets.get(dataset_id)
        if not dataset:
            return None
        return next((v for v in dataset.versions if v.is_active), None)

    def add_samples(self, dataset_id: str, samples: list[dict[str, Any]]) -> list[DatasetSample]:
        dataset = self._datasets.get(dataset_id)
        if not dataset or not dataset.latest_version:
            return []

        added_samples = []
        for sample_data in samples:
            sample = DatasetSample(
                id=sample_data.get("id", str(uuid4())[:8]),
                question=sample_data["question"],
                choices=sample_data.get("choices"),
                answer=sample_data.get("answer"),
                metadata=sample_data.get("metadata", {}),
            )
            dataset.latest_version.samples.append(sample)
            self._sample_index[sample.id] = sample
            added_samples.append(sample)

        dataset.updated_at = datetime.utcnow()
        return added_samples

    def remove_sample(self, dataset_id: str, sample_id: str) -> bool:
        dataset = self._datasets.get(dataset_id)
        if not dataset or not dataset.latest_version:
            return False

        original_count = len(dataset.latest_version.samples)
        dataset.latest_version.samples = [
            s for s in dataset.latest_version.samples if s.id != sample_id
        ]

        if sample_id in self._sample_index:
            del self._sample_index[sample_id]

        if len(dataset.latest_version.samples) < original_count:
            dataset.updated_at = datetime.utcnow()
            return True
        return False

    def get_sample(self, sample_id: str) -> DatasetSample | None:
        return self._sample_index.get(sample_id)

    def recycle_failed_samples(
        self,
        dataset_id: str,
        failed_sample_ids: list[str],
    ) -> list[DatasetSample]:
        dataset = self._datasets.get(dataset_id)
        if not dataset or not dataset.latest_version:
            return []

        recycled = []
        for sample_id in failed_sample_ids:
            sample = self.get_sample(sample_id)
            if sample:
                sample.metadata["recycled"] = True
                sample.metadata["recycled_at"] = datetime.utcnow().isoformat()
                sample.updated_at = datetime.utcnow()
                recycled.append(sample)

        if recycled:
            dataset.updated_at = datetime.utcnow()
        return recycled

    def search_samples(
        self,
        dataset_id: str,
        query: str,
        limit: int = 10,
    ) -> list[DatasetSample]:
        dataset = self._datasets.get(dataset_id)
        if not dataset or not dataset.latest_version:
            return []

        query_lower = query.lower()
        matched = [s for s in dataset.latest_version.samples if query_lower in s.question.lower()]
        return matched[:limit]

    def get_dataset_stats(self, dataset_id: str) -> dict[str, Any] | None:
        dataset = self._datasets.get(dataset_id)
        if not dataset:
            return None

        latest_version = dataset.latest_version
        if not latest_version:
            return None

        total_samples = len(latest_version.samples)
        with_answer = sum(1 for s in latest_version.samples if s.answer)
        recycled = sum(1 for s in latest_version.samples if s.metadata.get("recycled"))

        return {
            "dataset_id": dataset.id,
            "dataset_name": dataset.name,
            "version": latest_version.version_number,
            "total_samples": total_samples,
            "samples_with_answer": with_answer,
            "samples_without_answer": total_samples - with_answer,
            "recycled_samples": recycled,
            "version_count": len(dataset.versions),
        }

    def detect_duplicates(
        self, dataset_id: str, similarity_threshold: float = 0.8
    ) -> list[dict[str, Any]]:
        dataset = self._datasets.get(dataset_id)
        if not dataset or not dataset.latest_version:
            return []

        samples = dataset.latest_version.samples
        duplicates = []
        seen_hashes = {}

        for i, sample in enumerate(samples):
            text_hash = self._compute_text_hash(sample.question)

            if text_hash in seen_hashes:
                duplicates.append(
                    {
                        "duplicate_id": sample.id,
                        "original_id": seen_hashes[text_hash]["id"],
                        "duplicate_index": i,
                        "original_index": seen_hashes[text_hash]["index"],
                        "similarity": 1.0,
                        "reason": "完全重复",
                    }
                )
            else:
                for j in range(i):
                    other_sample = samples[j]
                    similarity = self._calculate_similarity(sample.question, other_sample.question)
                    if similarity >= similarity_threshold:
                        duplicates.append(
                            {
                                "duplicate_id": sample.id,
                                "original_id": other_sample.id,
                                "duplicate_index": i,
                                "original_index": j,
                                "similarity": similarity,
                                "reason": f"相似度超过阈值 {similarity_threshold}",
                            }
                        )
                        break
                seen_hashes[text_hash] = {"id": sample.id, "index": i}

        return duplicates

    def remove_duplicates(self, dataset_id: str, similarity_threshold: float = 0.8) -> int:
        duplicates = self.detect_duplicates(dataset_id, similarity_threshold)
        if not duplicates:
            return 0

        dataset = self._datasets.get(dataset_id)
        if not dataset or not dataset.latest_version:
            return 0

        duplicate_ids = {d["duplicate_id"] for d in duplicates}
        original_count = len(dataset.latest_version.samples)

        dataset.latest_version.samples = [
            s for s in dataset.latest_version.samples if s.id not in duplicate_ids
        ]

        for sample_id in duplicate_ids:
            if sample_id in self._sample_index:
                del self._sample_index[sample_id]

        dataset.updated_at = datetime.utcnow()

        return original_count - len(dataset.latest_version.samples)

    def check_contamination(self, dataset_id: str, external_text: str) -> dict[str, Any]:
        dataset = self._datasets.get(dataset_id)
        if not dataset or not dataset.latest_version:
            return {"contaminated": False, "matches": []}

        samples = dataset.latest_version.samples
        matches = []

        for sample in samples:
            similarity = self._calculate_similarity(sample.question, external_text)
            if similarity > 0.7:
                matches.append(
                    {
                        "sample_id": sample.id,
                        "question": (
                            sample.question[:100] + "..."
                            if len(sample.question) > 100
                            else sample.question
                        ),
                        "similarity": similarity,
                    }
                )

        return {
            "contaminated": len(matches) > 0,
            "match_count": len(matches),
            "matches": matches[:10],
        }

    def _compute_text_hash(self, text: str) -> str:
        import hashlib

        normalized = text.strip().lower().replace("\n", " ").replace("\r", "")
        return hashlib.md5(normalized.encode()).hexdigest()

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        from difflib import SequenceMatcher

        return SequenceMatcher(None, text1, text2).ratio()

    def update_version_periodically(self, dataset_id: str, max_age_days: int = 30) -> bool:
        dataset = self._datasets.get(dataset_id)
        if not dataset:
            return False

        if not dataset.versions:
            return False

        latest_version = dataset.latest_version
        age_days = (datetime.utcnow() - latest_version.created_at).days

        if age_days >= max_age_days:
            self.create_version(
                dataset_id=dataset_id,
                samples=[s.to_dict() for s in latest_version.samples],
                description=f"自动更新版本（超过{max_age_days}天）",
            )
            return True

        return False

    def fold_memory(self, dataset_id: str, max_context_length: int = 8192) -> dict[str, Any]:
        dataset = self._datasets.get(dataset_id)
        if not dataset or not dataset.latest_version:
            return {"folded_count": 0, "original_size": 0, "folded_size": 0}

        samples = dataset.latest_version.samples
        original_size = sum(len(s.question) + (len(s.answer) if s.answer else 0) for s in samples)

        folded_count = 0
        for sample in samples:
            question_length = len(sample.question)
            if question_length > max_context_length:
                sample.question = sample.question[:max_context_length]
                sample.metadata["folded"] = True
                sample.metadata["original_length"] = question_length
                sample.metadata["folded_at"] = datetime.utcnow().isoformat()
                sample.updated_at = datetime.utcnow()
                folded_count += 1

        if folded_count > 0:
            dataset.updated_at = datetime.utcnow()

        folded_size = sum(len(s.question) + (len(s.answer) if s.answer else 0) for s in samples)

        return {
            "folded_count": folded_count,
            "original_size": original_size,
            "folded_size": folded_size,
            "reduction_ratio": (
                (original_size - folded_size) / original_size if original_size > 0 else 0
            ),
        }

    def create_summary_memory(self, dataset_id: str) -> dict[str, Any] | None:
        dataset = self._datasets.get(dataset_id)
        if not dataset or not dataset.latest_version:
            return None

        samples = dataset.latest_version.samples
        if not samples:
            return None

        summary = {
            "dataset_id": dataset.id,
            "dataset_name": dataset.name,
            "total_samples": len(samples),
            "categories": {},
            "difficulty_distribution": {},
            "average_length": sum(len(s.question) for s in samples) / len(samples),
        }

        for sample in samples:
            category = sample.metadata.get("category", "unknown")
            summary["categories"][category] = summary["categories"].get(category, 0) + 1

            difficulty = sample.metadata.get("difficulty", "medium")
            summary["difficulty_distribution"][difficulty] = (
                summary["difficulty_distribution"].get(difficulty, 0) + 1
            )

        summary["created_at"] = datetime.utcnow().isoformat()

        if "summary" not in dataset.metadata:
            dataset.metadata["summary"] = {}
        dataset.metadata["summary"][dataset.latest_version.version_number] = summary

        return summary
