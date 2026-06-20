from dataclasses import dataclass, field
from typing import Any, Protocol


class BaseBenchmark(Protocol):
    name: str
    description: str
    category: str
    num_samples: int

    def load_dataset(self) -> list[dict[str, Any]]:
        ...

    def evaluate(self, llm_client, samples: list[dict[str, Any]] | None = None) -> "BenchmarkResult":
        ...

    def calculate_score(self, results: list[dict[str, Any]]) -> float:
        ...


@dataclass
class BenchmarkResult:
    benchmark_name: str
    total_samples: int
    correct_samples: int
    accuracy: float
    scores: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    error_count: int = 0
    error_messages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark_name": self.benchmark_name,
            "total_samples": self.total_samples,
            "correct_samples": self.correct_samples,
            "accuracy": self.accuracy,
            "scores": self.scores,
            "metadata": self.metadata,
            "error_count": self.error_count,
            "error_messages": self.error_messages,
        }
