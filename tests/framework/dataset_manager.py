import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from tests.framework.test_layer import (
    AgentDecisionTestCase,
    LLMTestCase,
    MultiAgentTestCase,
    ToolCallTestCase,
)


@dataclass
class DatasetMetadata:
    name: str
    version: str
    description: str
    layer: str
    test_type: str
    created_at: str
    updated_at: str
    size: int
    tags: List[str] = field(default_factory=list)


class DatasetManager:
    def __init__(self, base_dir: str = "tests/datasets"):
        self.base_dir = base_dir
        self._ensure_dir(base_dir)

    def _ensure_dir(self, path: str):
        os.makedirs(path, exist_ok=True)

    def _get_dataset_path(self, dataset_name: str) -> str:
        return os.path.join(self.base_dir, f"{dataset_name}.json")

    def save_dataset(
        self,
        dataset_name: str,
        cases: List[
            Union[LLMTestCase, AgentDecisionTestCase, ToolCallTestCase, MultiAgentTestCase]
        ],
        description: str = "",
        layer: str = "llm_capability",
        test_type: str = "normal",
        tags: Optional[List[str]] = None,
    ):
        import time

        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
        metadata = DatasetMetadata(
            name=dataset_name,
            version="1.0.0",
            description=description,
            layer=layer,
            test_type=test_type,
            created_at=timestamp,
            updated_at=timestamp,
            size=len(cases),
            tags=tags or [],
        )

        data = {
            "metadata": metadata.__dict__,
            "cases": [case.__dict__ for case in cases],
        }

        with open(self._get_dataset_path(dataset_name), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_dataset(self, dataset_name: str) -> Dict[str, Any]:
        path = self._get_dataset_path(dataset_name)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Dataset {dataset_name} not found")

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_datasets(self) -> List[DatasetMetadata]:
        datasets = []
        for filename in os.listdir(self.base_dir):
            if filename.endswith(".json"):
                dataset_name = filename[:-5]
                try:
                    data = self.load_dataset(dataset_name)
                    metadata = DatasetMetadata(**data["metadata"])
                    datasets.append(metadata)
                except Exception:
                    continue
        return datasets

    def delete_dataset(self, dataset_name: str):
        path = self._get_dataset_path(dataset_name)
        if os.path.exists(path):
            os.remove(path)

    def create_llm_dataset(
        self,
        dataset_name: str,
        cases: List[Dict[str, Any]],
        description: str = "",
        tags: Optional[List[str]] = None,
    ):
        llm_cases = [LLMTestCase(**case) for case in cases]
        self.save_dataset(dataset_name, llm_cases, description, "llm_capability", "normal", tags)

    def create_agent_decision_dataset(
        self,
        dataset_name: str,
        cases: List[Dict[str, Any]],
        description: str = "",
        tags: Optional[List[str]] = None,
    ):
        agent_cases = [AgentDecisionTestCase(**case) for case in cases]
        self.save_dataset(
            dataset_name, agent_cases, description, "agent_decision", "normal", tags
        )

    def create_tool_calling_dataset(
        self,
        dataset_name: str,
        cases: List[Dict[str, Any]],
        description: str = "",
        tags: Optional[List[str]] = None,
    ):
        tool_cases = [ToolCallTestCase(**case) for case in cases]
        self.save_dataset(dataset_name, tool_cases, description, "tool_calling", "normal", tags)

    def create_multi_agent_dataset(
        self,
        dataset_name: str,
        cases: List[Dict[str, Any]],
        description: str = "",
        tags: Optional[List[str]] = None,
    ):
        multi_cases = [MultiAgentTestCase(**case) for case in cases]
        self.save_dataset(dataset_name, multi_cases, description, "multi_agent", "normal", tags)

    def split_dataset(
        self, dataset_name: str, train_ratio: float = 0.8, shuffle: bool = True
    ) -> Dict[str, Any]:
        data = self.load_dataset(dataset_name)
        cases = data["cases"]

        if shuffle:
            import random

            random.shuffle(cases)

        split_idx = int(len(cases) * train_ratio)
        train_cases = cases[:split_idx]
        test_cases = cases[split_idx:]

        return {
            "train": {"metadata": data["metadata"], "cases": train_cases},
            "test": {"metadata": data["metadata"], "cases": test_cases},
        }

    def merge_datasets(self, *dataset_names: str, output_name: str):
        merged_cases = []
        merged_metadata = None

        for name in dataset_names:
            data = self.load_dataset(name)
            merged_cases.extend(data["cases"])
            if merged_metadata is None:
                merged_metadata = data["metadata"]

        if merged_metadata:
            merged_metadata["size"] = len(merged_cases)
            merged_metadata["name"] = output_name

        data = {
            "metadata": merged_metadata,
            "cases": merged_cases,
        }

        with open(self._get_dataset_path(output_name), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)