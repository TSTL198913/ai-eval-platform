import json
import os
from datetime import datetime
from typing import Any

from src.domain.golden_dataset import golden_dataset_manager


class CalibrationService:
    def __init__(self):
        self._calibration_data_dir = "data/calibration"
        os.makedirs(self._calibration_data_dir, exist_ok=True)

    def create_golden_dataset(
        self, name: str, description: str = "", category: str = "general"
    ) -> dict[str, Any]:
        dataset = golden_dataset_manager.create_dataset(name, description, category)
        return dataset.to_dict()

    def add_golden_sample(
        self, dataset_id: str, sample_data: dict[str, Any]
    ) -> dict[str, Any] | None:
        sample = golden_dataset_manager.add_sample(dataset_id, sample_data)
        return sample.to_dict() if sample else None

    def correct_evaluation(
        self, sample_id: str, corrected_scores: dict[str, float], corrected_by: str = "user"
    ) -> dict[str, Any] | None:
        sample = golden_dataset_manager.correct_sample(sample_id, corrected_scores, corrected_by)
        return sample.to_dict() if sample else None

    def get_few_shot_examples(self, dataset_id: str, limit: int = 5) -> list[str]:
        return golden_dataset_manager.get_few_shot_examples(dataset_id, limit)

    def get_calibration_stats(self, dataset_id: str) -> dict[str, Any] | None:
        dataset = golden_dataset_manager.get_dataset(dataset_id)
        if not dataset:
            return None
        return {
            "dataset_id": dataset.id,
            "name": dataset.name,
            "total_samples": len(dataset.samples),
            "corrected_samples": dataset.corrected_count,
            "uncorrected_samples": len(dataset.samples) - dataset.corrected_count,
        }

    def list_golden_datasets(self) -> list[dict[str, Any]]:
        return [d.to_dict() for d in golden_dataset_manager.list_datasets()]

    def export_calibration_data(self, dataset_id: str) -> str:
        dataset = golden_dataset_manager.get_dataset(dataset_id)
        if not dataset:
            return ""
        export_data = {
            "dataset_id": dataset.id,
            "name": dataset.name,
            "description": dataset.description,
            "category": dataset.category,
            "exported_at": datetime.utcnow().isoformat(),
            "samples": [s.to_dict() for s in dataset.samples],
        }
        filepath = os.path.join(
            self._calibration_data_dir,
            f"{dataset_id}_export_{int(datetime.utcnow().timestamp())}.json",
        )
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        return filepath

    def import_calibration_data(self, filepath: str) -> bool:
        if not os.path.exists(filepath):
            return False
        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
            dataset = golden_dataset_manager.create_dataset(
                name=data.get("name", "imported"),
                description=data.get("description", ""),
                category=data.get("category", "general"),
            )
            for sample_data in data.get("samples", []):
                golden_dataset_manager.add_sample(dataset.id, sample_data)
            return True
        except Exception:
            return False


calibration_service = CalibrationService()
