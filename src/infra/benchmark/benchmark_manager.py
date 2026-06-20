import json
import os
from typing import Any

from pydantic import BaseModel, Field

from src.config import settings


class BenchmarkDataset(BaseModel):
    dataset_id: str = Field(..., description="数据集唯一标识")
    name: str = Field(..., description="数据集名称")
    category: str = Field(..., description="数据集类别")
    description: str = Field("", description="数据集描述")
    questions: list[dict[str, Any]] = Field(default_factory=list)
    version: str = Field("1.0", description="版本号")
    created_at: str = Field("", description="创建时间")
    source: str = Field("", description="数据源")


class BenchmarkResult(BaseModel):
    benchmark_id: str = Field(..., description="评测唯一标识")
    dataset_id: str = Field(..., description="数据集ID")
    model_name: str = Field(..., description="模型名称")
    total_questions: int = Field(0, description="总题目数")
    correct_count: int = Field(0, description="正确数")
    accuracy: float = Field(0.0, description="准确率")
    avg_latency_ms: float = Field(0.0, description="平均延迟")
    total_tokens: int = Field(0, description="总Token数")
    cost_usd: float = Field(0.0, description="成本")
    detailed_results: list[dict[str, Any]] = Field(default_factory=list)
    timestamp: str = Field("", description="评测时间")


class BenchmarkManager:
    """Benchmark 基准测试管理器

    管理评测数据集、运行基准测试、生成报告。
    """

    def __init__(self):
        self.datasets: dict[str, BenchmarkDataset] = {}
        self.results: dict[str, BenchmarkResult] = {}
        self.datasets_dir = os.path.join(settings.app_name, "benchmark_datasets")
        os.makedirs(self.datasets_dir, exist_ok=True)
        self._load_datasets()

    def _load_datasets(self):
        for filename in os.listdir(self.datasets_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(self.datasets_dir, filename)
                try:
                    with open(filepath, encoding="utf-8") as f:
                        data = json.load(f)
                        dataset = BenchmarkDataset(**data)
                        self.datasets[dataset.dataset_id] = dataset
                except Exception as e:
                    print(f"加载数据集 {filename} 失败: {e}")

    def add_dataset(self, dataset: BenchmarkDataset) -> bool:
        self.datasets[dataset.dataset_id] = dataset
        filepath = os.path.join(self.datasets_dir, f"{dataset.dataset_id}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(dataset.model_dump(), f, ensure_ascii=False, indent=2)
        return True

    def get_dataset(self, dataset_id: str) -> BenchmarkDataset | None:
        return self.datasets.get(dataset_id)

    def list_datasets(self) -> list[dict[str, Any]]:
        return [
            {
                "dataset_id": ds.dataset_id,
                "name": ds.name,
                "category": ds.category,
                "questions_count": len(ds.questions),
                "version": ds.version,
            }
            for ds in self.datasets.values()
        ]

    def run_benchmark(
        self,
        dataset_id: str,
        model_name: str,
        evaluator_fn,
        **kwargs,
    ) -> BenchmarkResult:
        dataset = self.get_dataset(dataset_id)
        if not dataset:
            raise ValueError(f"数据集 {dataset_id} 不存在")

        import time
        import uuid

        benchmark_id = f"benchmark-{uuid.uuid4().hex[:8]}"
        detailed_results = []
        correct_count = 0
        total_latency_ms = 0
        total_tokens = 0

        for i, question in enumerate(dataset.questions):
            start_time = time.time()
            try:
                result = evaluator_fn(question, **kwargs)
                latency_ms = (time.time() - start_time) * 1000
                total_latency_ms += latency_ms
                total_tokens += result.get("token_usage", 0)

                is_correct = result.get("is_valid", False) and result.get("score", 0) >= 0.8
                if is_correct:
                    correct_count += 1

                detailed_results.append({
                    "question_id": question.get("id", f"q-{i}"),
                    "input": question.get("input", ""),
                    "expected_output": question.get("expected_output", ""),
                    "actual_output": result.get("text", ""),
                    "score": result.get("score", 0),
                    "is_correct": is_correct,
                    "latency_ms": latency_ms,
                })
            except Exception as e:
                detailed_results.append({
                    "question_id": question.get("id", f"q-{i}"),
                    "input": question.get("input", ""),
                    "error": str(e),
                    "is_correct": False,
                    "latency_ms": (time.time() - start_time) * 1000,
                })

        accuracy = correct_count / len(dataset.questions) if dataset.questions else 0
        avg_latency_ms = total_latency_ms / len(dataset.questions) if dataset.questions else 0
        cost_usd = total_tokens * 0.000002

        result = BenchmarkResult(
            benchmark_id=benchmark_id,
            dataset_id=dataset_id,
            model_name=model_name,
            total_questions=len(dataset.questions),
            correct_count=correct_count,
            accuracy=accuracy,
            avg_latency_ms=avg_latency_ms,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            detailed_results=detailed_results,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )

        self.results[benchmark_id] = result
        return result

    def get_result(self, benchmark_id: str) -> BenchmarkResult | None:
        return self.results.get(benchmark_id)

    def list_results(self) -> list[dict[str, Any]]:
        return [
            {
                "benchmark_id": r.benchmark_id,
                "dataset_id": r.dataset_id,
                "model_name": r.model_name,
                "accuracy": r.accuracy,
                "avg_latency_ms": r.avg_latency_ms,
                "total_tokens": r.total_tokens,
                "cost_usd": r.cost_usd,
                "timestamp": r.timestamp,
            }
            for r in self.results.values()
        ]


benchmark_manager = BenchmarkManager()
