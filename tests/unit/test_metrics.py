import pytest

from src.domain.metrics.collector import EvaluationMetrics, MetricsCollector, GlobalMetricsCollector


class TestEvaluationMetrics:
    def test_initial_state(self):
        metrics = EvaluationMetrics(task_id="test-1", evaluator_type="test")
        assert metrics.task_id == "test-1"
        assert metrics.evaluator_type == "test"
        assert metrics.task_success is False
        assert metrics.decision_count == 0
        assert metrics.correct_decisions == 0
        assert metrics.hallucination_count == 0
        assert metrics.decision_accuracy == 0.0
        assert metrics.hallucination_rate == 0.0

    def test_decision_accuracy(self):
        metrics = EvaluationMetrics(task_id="test-1", evaluator_type="test")
        metrics.decision_count = 10
        metrics.correct_decisions = 7
        assert metrics.decision_accuracy == 0.7

    def test_hallucination_rate(self):
        metrics = EvaluationMetrics(task_id="test-1", evaluator_type="test")
        metrics.decision_count = 10
        metrics.hallucination_count = 2
        assert metrics.hallucination_rate == pytest.approx(0.1667, abs=0.0001)

    def test_tool_call_accuracy(self):
        metrics = EvaluationMetrics(task_id="test-1", evaluator_type="test")
        metrics.tool_calls = 5
        metrics.correct_tool_calls = 4
        assert metrics.tool_call_accuracy == 0.8

    def test_to_dict(self):
        metrics = EvaluationMetrics(task_id="test-1", evaluator_type="test")
        metrics.decision_count = 10
        metrics.correct_decisions = 7
        metrics.hallucination_count = 2
        metrics.tool_calls = 5
        metrics.correct_tool_calls = 4
        metrics.task_success = True
        metrics.latency_ms = 123.45

        result = metrics.to_dict()
        assert result["task_id"] == "test-1"
        assert result["task_success"] is True
        assert result["decision_accuracy"] == 0.7
        assert result["hallucination_rate"] == pytest.approx(0.1667, abs=0.0001)
        assert result["tool_call_accuracy"] == 0.8


class TestMetricsCollector:
    def test_start_task(self):
        collector = MetricsCollector()
        metrics = collector.start_task("task-1", "evaluator")
        assert metrics.task_id == "task-1"
        assert metrics.evaluator_type == "evaluator"

    def test_record_decision(self):
        collector = MetricsCollector()
        collector.start_task("task-1", "evaluator")
        collector.record_decision("task-1", True)
        collector.record_decision("task-1", False)
        collector.record_decision("task-1", True)

        metrics = collector.get_metrics("task-1")
        assert metrics.decision_count == 3
        assert metrics.correct_decisions == 2
        assert metrics.decision_accuracy == 2/3

    def test_record_hallucination(self):
        collector = MetricsCollector()
        collector.start_task("task-1", "evaluator")
        collector.record_hallucination("task-1")
        collector.record_hallucination("task-1")

        metrics = collector.get_metrics("task-1")
        assert metrics.hallucination_count == 2

    def test_record_tool_call(self):
        collector = MetricsCollector()
        collector.start_task("task-1", "evaluator")
        collector.record_tool_call("task-1", True)
        collector.record_tool_call("task-1", False)

        metrics = collector.get_metrics("task-1")
        assert metrics.tool_calls == 2
        assert metrics.correct_tool_calls == 1

    def test_complete_task(self):
        collector = MetricsCollector()
        collector.start_task("task-1", "evaluator")
        collector.complete_task("task-1", success=True, latency_ms=500.0)

        metrics = collector.get_metrics("task-1")
        assert metrics.task_success is True
        assert metrics.latency_ms == 500.0

    def test_get_all_metrics(self):
        collector = MetricsCollector()
        collector.start_task("task-1", "evaluator")
        collector.start_task("task-2", "evaluator")

        all_metrics = collector.get_all_metrics()
        assert len(all_metrics) == 2

    def test_clear(self):
        collector = MetricsCollector()
        collector.start_task("task-1", "evaluator")
        collector.clear()

        assert len(collector.get_all_metrics()) == 0

    def test_get_nonexistent_metrics(self):
        collector = MetricsCollector()
        assert collector.get_metrics("nonexistent") is None


class TestGlobalMetricsCollector:
    def test_singleton(self):
        instance1 = GlobalMetricsCollector()
        instance2 = GlobalMetricsCollector()
        assert instance1 is instance2

    def test_delegation(self):
        collector = GlobalMetricsCollector()
        collector.start_task("task-1", "evaluator")
        collector.record_decision("task-1", True)

        metrics = collector.get_metrics("task-1")
        assert metrics.decision_count == 1
        assert metrics.correct_decisions == 1
