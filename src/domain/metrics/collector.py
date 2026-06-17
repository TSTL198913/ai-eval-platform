from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class EvaluationMetrics:
    task_id: str
    evaluator_type: str
    task_success: bool = False
    decision_count: int = 0
    correct_decisions: int = 0
    hallucination_count: int = 0
    total_steps: int = 0
    token_consumption: int = 0
    latency_ms: float = 0.0
    tool_calls: int = 0
    correct_tool_calls: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def decision_accuracy(self) -> float:
        return self.correct_decisions / self.decision_count if self.decision_count > 0 else 0.0

    @property
    def hallucination_rate(self) -> float:
        total = self.decision_count + self.hallucination_count
        return self.hallucination_count / total if total > 0 else 0.0

    @property
    def tool_call_accuracy(self) -> float:
        return self.correct_tool_calls / self.tool_calls if self.tool_calls > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "evaluator_type": self.evaluator_type,
            "task_success": self.task_success,
            "decision_count": self.decision_count,
            "correct_decisions": self.correct_decisions,
            "decision_accuracy": self.decision_accuracy,
            "hallucination_count": self.hallucination_count,
            "hallucination_rate": self.hallucination_rate,
            "total_steps": self.total_steps,
            "token_consumption": self.token_consumption,
            "latency_ms": self.latency_ms,
            "tool_calls": self.tool_calls,
            "correct_tool_calls": self.correct_tool_calls,
            "tool_call_accuracy": self.tool_call_accuracy,
            "metadata": self.metadata,
        }


class MetricsCollector:
    def __init__(self):
        self._metrics_store: Dict[str, EvaluationMetrics] = {}

    def start_task(self, task_id: str, evaluator_type: str) -> EvaluationMetrics:
        metrics = EvaluationMetrics(task_id=task_id, evaluator_type=evaluator_type)
        self._metrics_store[task_id] = metrics
        return metrics

    def record_decision(self, task_id: str, is_correct: bool):
        if task_id in self._metrics_store:
            self._metrics_store[task_id].decision_count += 1
            if is_correct:
                self._metrics_store[task_id].correct_decisions += 1

    def record_hallucination(self, task_id: str):
        if task_id in self._metrics_store:
            self._metrics_store[task_id].hallucination_count += 1

    def record_tool_call(self, task_id: str, is_correct: bool):
        if task_id in self._metrics_store:
            self._metrics_store[task_id].tool_calls += 1
            if is_correct:
                self._metrics_store[task_id].correct_tool_calls += 1

    def complete_task(self, task_id: str, success: bool, latency_ms: float = 0.0):
        if task_id in self._metrics_store:
            self._metrics_store[task_id].task_success = success
            self._metrics_store[task_id].latency_ms = latency_ms

    def get_metrics(self, task_id: str) -> Optional[EvaluationMetrics]:
        return self._metrics_store.get(task_id)

    def get_all_metrics(self) -> List[EvaluationMetrics]:
        return list(self._metrics_store.values())

    def clear(self):
        self._metrics_store.clear()


class GlobalMetricsCollector:
    _instance: Optional["GlobalMetricsCollector"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.collector = MetricsCollector()
        return cls._instance

    def __getattr__(self, name):
        return getattr(self.collector, name)
