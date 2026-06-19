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
    def __init__(self, persist: bool = True):
        self._metrics_store: Dict[str, EvaluationMetrics] = {}
        self._persist = persist
        # 加载历史持久化数据
        if self._persist:
            self._load_from_disk()

    def start_task(self, task_id: str, evaluator_type: str) -> EvaluationMetrics:
        metrics = EvaluationMetrics(task_id=task_id, evaluator_type=evaluator_type)
        self._metrics_store[task_id] = metrics
        return metrics

    def record_decision(self, task_id: str, is_correct: bool):
        if task_id in self._metrics_store:
            self._metrics_store[task_id].decision_count += 1
            if is_correct:
                self._metrics_store[task_id].correct_decisions += 1
        self._persist_async()

    def record_hallucination(self, task_id: str):
        if task_id in self._metrics_store:
            self._metrics_store[task_id].hallucination_count += 1
        self._persist_async()

    def record_tool_call(self, task_id: str, is_correct: bool):
        if task_id in self._metrics_store:
            self._metrics_store[task_id].tool_calls += 1
            if is_correct:
                self._metrics_store[task_id].correct_tool_calls += 1
        self._persist_async()

    def complete_task(self, task_id: str, success: bool, latency_ms: float = 0.0):
        if task_id in self._metrics_store:
            self._metrics_store[task_id].task_success = success
            self._metrics_store[task_id].latency_ms = latency_ms
        # 完成时强制持久化到数据库
        if self._persist:
            self._persist_to_repository(task_id)

    def get_metrics(self, task_id: str) -> Optional[EvaluationMetrics]:
        return self._metrics_store.get(task_id)

    def get_all_metrics(self) -> List[EvaluationMetrics]:
        return list(self._metrics_store.values())

    def clear(self):
        self._metrics_store.clear()

    def _persist_async(self) -> None:
        """异步持久化（内存级）"""
        if not self._persist:
            return
        try:
            import json
            from pathlib import Path
            metrics_file = Path("data/metrics_store.json")
            metrics_file.parent.mkdir(parents=True, exist_ok=True)
            data = {tid: m.to_dict() for tid, m in self._metrics_store.items()}
            metrics_file.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        except Exception:
            pass

    def _persist_to_repository(self, task_id: str) -> None:
        """持久化到EvaluationRepository"""
        try:
            from src.infra.db.repository import EvaluationRepository
            repo = EvaluationRepository()
            metrics = self._metrics_store.get(task_id)
            if metrics:
                # 将指标数据写入评估记录表
                repo.save({
                    "task_id": task_id,
                    "evaluator_type": metrics.evaluator_type,
                    "score": 1.0 if metrics.task_success else 0.0,
                    "decision_accuracy": metrics.decision_accuracy,
                    "hallucination_rate": metrics.hallucination_rate,
                    "tool_call_accuracy": metrics.tool_call_accuracy,
                    "total_tokens": metrics.token_consumption,
                    "latency_ms": metrics.latency_ms,
                    "metadata": metrics.metadata,
                })
        except Exception:
            # 静默失败，不影响主流程
            pass

    def _load_from_disk(self) -> None:
        """从磁盘加载历史数据"""
        try:
            import json
            from pathlib import Path
            metrics_file = Path("data/metrics_store.json")
            if metrics_file.exists():
                data = json.loads(metrics_file.read_text(encoding="utf-8"))
                for tid, m_dict in data.items():
                    metrics = EvaluationMetrics(
                        task_id=m_dict.get("task_id", tid),
                        evaluator_type=m_dict.get("evaluator_type", "unknown"),
                        task_success=m_dict.get("task_success", False),
                        decision_count=m_dict.get("decision_count", 0),
                        correct_decisions=m_dict.get("correct_decisions", 0),
                        hallucination_count=m_dict.get("hallucination_count", 0),
                        total_steps=m_dict.get("total_steps", 0),
                        token_consumption=m_dict.get("token_consumption", 0),
                        latency_ms=m_dict.get("latency_ms", 0.0),
                        tool_calls=m_dict.get("tool_calls", 0),
                        correct_tool_calls=m_dict.get("correct_tool_calls", 0),
                        metadata=m_dict.get("metadata", {}),
                    )
                    self._metrics_store[tid] = metrics
        except Exception:
            pass


class GlobalMetricsCollector:
    _instance: Optional["GlobalMetricsCollector"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.collector = MetricsCollector()
        return cls._instance

    def __getattr__(self, name):
        return getattr(self.collector, name)
