from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol


class BaseBenchmark(Protocol):
    name: str
    description: str
    category: str
    num_samples: int

    def load_dataset(self) -> List[Dict[str, Any]]:
        ...

    def evaluate(self, llm_client, samples: Optional[List[Dict[str, Any]]] = None) -> "BenchmarkResult":
        ...

    def calculate_score(self, results: List[Dict[str, Any]]) -> float:
        ...


@dataclass
class BenchmarkResult:
    benchmark_name: str
    total_samples: int
    correct_samples: int
    accuracy: float
    scores: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_count: int = 0
    error_messages: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
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
