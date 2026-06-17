import pytest

from src.domain.benchmarks import BenchmarkRegistry, MMLUBenchmark, GSM8KBenchmark
from src.domain.benchmarks.base import BenchmarkResult


class MockLLMClient:
    def __init__(self, answers):
        self.answers = answers
        self.call_count = 0

    def chat_completion(self, prompt):
        self.call_count += 1
        return self.answers[self.call_count - 1] if self.call_count <= len(self.answers) else "A"


class TestBenchmarkRegistry:
    def test_register_and_get(self):
        assert BenchmarkRegistry.get("mmlu") == MMLUBenchmark
        assert BenchmarkRegistry.get("gsm8k") == GSM8KBenchmark

    def test_list_benchmarks(self):
        benchmarks = BenchmarkRegistry.list()
        assert "mmlu" in benchmarks
        assert "gsm8k" in benchmarks

    def test_get_info(self):
        info = BenchmarkRegistry.get_info("mmlu")
        assert info["name"] == "MMLU"
        assert info["category"] == "knowledge"


class TestMMLUBenchmark:
    def test_load_dataset(self):
        benchmark = MMLUBenchmark()
        dataset = benchmark.load_dataset()
        assert len(dataset) > 0
        assert "question" in dataset[0]
        assert "choices" in dataset[0]
        assert "answer" in dataset[0]

    def test_evaluate(self):
        benchmark = MMLUBenchmark()
        mock_client = MockLLMClient(["B", "B", "B", "B", "B"])
        samples = [
            {"question": "Test", "choices": ["A. X", "B. Y", "C. Z", "D. W"], "answer": "B", "id": 0, "subject": "test"},
            {"question": "Test", "choices": ["A. X", "B. Y", "C. Z", "D. W"], "answer": "B", "id": 1, "subject": "test"},
        ]
        result = benchmark.evaluate(mock_client, samples)
        assert result.total_samples == 2
        assert result.correct_samples == 2
        assert result.accuracy == 1.0

    def test_build_prompt(self):
        benchmark = MMLUBenchmark()
        sample = {"question": "What is 2+2?", "choices": ["A. 3", "B. 4", "C. 5"]}
        prompt = benchmark._build_prompt(sample)
        assert "What is 2+2?" in prompt
        assert "A. 3" in prompt

    def test_parse_answer(self):
        benchmark = MMLUBenchmark()
        assert benchmark._parse_answer("The answer is B") == "B"
        assert benchmark._parse_answer("B") == "B"
        assert benchmark._parse_answer("1. A, 2. B") == "B"


class TestGSM8KBenchmark:
    def test_load_dataset(self):
        benchmark = GSM8KBenchmark()
        dataset = benchmark.load_dataset()
        assert len(dataset) > 0
        assert "question" in dataset[0]
        assert "answer" in dataset[0]

    def test_evaluate(self):
        benchmark = GSM8KBenchmark()
        mock_client = MockLLMClient(["8", "180", "3"])
        samples = [
            {"question": "Test", "answer": "8", "id": 0},
            {"question": "Test", "answer": "180", "id": 1},
        ]
        result = benchmark.evaluate(mock_client, samples)
        assert result.total_samples == 2
        assert result.correct_samples == 2

    def test_parse_answer(self):
        benchmark = GSM8KBenchmark()
        assert benchmark._parse_answer("The answer is 42") == "42"
        assert benchmark._parse_answer("42") == "42"
        assert benchmark._parse_answer("Result: 3.14") == "3.14"

    def test_compare_answers(self):
        benchmark = GSM8KBenchmark()
        assert benchmark._compare_answers("42", "42") is True
        assert benchmark._compare_answers("42", "42.0") is True
        assert benchmark._compare_answers("42", "43") is False


class TestBenchmarkResult:
    def test_to_dict(self):
        result = BenchmarkResult(
            benchmark_name="test",
            total_samples=10,
            correct_samples=8,
            accuracy=0.8,
        )
        result_dict = result.to_dict()
        assert result_dict["benchmark_name"] == "test"
        assert result_dict["accuracy"] == 0.8
