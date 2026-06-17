import pytest
from unittest.mock import MagicMock

from src.domain.benchmarks.mmlu import MMLUBenchmark
from src.domain.benchmarks.base import BenchmarkResult


class MockLLMClient:
    def __init__(self, answers):
        self.answers = answers
        self.call_count = 0

    def chat_completion(self, prompt):
        self.call_count += 1
        idx = self.call_count - 1
        return self.answers[idx] if idx < len(self.answers) else 'A'


class TestMMLUBenchmark:
    def test_evaluate_all_correct(self):
        benchmark = MMLUBenchmark()
        mock_client = MockLLMClient(['A', 'B'])
        samples = [
            {'question': 'Test Q1', 'choices': ['A. X', 'B. Y'], 'answer': 'A', 'id': 0, 'subject': 'test'},
            {'question': 'Test Q2', 'choices': ['A. X', 'B. Y'], 'answer': 'B', 'id': 1, 'subject': 'test'},
        ]
        result = benchmark.evaluate(mock_client, samples)
        assert result.total_samples == 2
        assert result.correct_samples == 2
        assert result.accuracy == 1.0

    def test_evaluate_all_wrong(self):
        benchmark = MMLUBenchmark()
        mock_client = MockLLMClient(['B', 'A'])
        samples = [
            {'question': 'Test Q1', 'choices': ['A. X', 'B. Y'], 'answer': 'A', 'id': 0, 'subject': 'test'},
            {'question': 'Test Q2', 'choices': ['A. X', 'B. Y'], 'answer': 'B', 'id': 1, 'subject': 'test'},
        ]
        result = benchmark.evaluate(mock_client, samples)
        assert result.accuracy == 0.0

    def test_evaluate_partial_correct(self):
        benchmark = MMLUBenchmark()
        mock_client = MockLLMClient(['A', 'A'])
        samples = [
            {'question': 'Test Q1', 'choices': ['A. X', 'B. Y'], 'answer': 'A', 'id': 0, 'subject': 'test'},
            {'question': 'Test Q2', 'choices': ['A. X', 'B. Y'], 'answer': 'B', 'id': 1, 'subject': 'test'},
        ]
        result = benchmark.evaluate(mock_client, samples)
        assert result.correct_samples == 1
        assert result.accuracy == 0.5

    def test_evaluate_empty_samples(self):
        benchmark = MMLUBenchmark()
        mock_client = MockLLMClient([])
        result = benchmark.evaluate(mock_client, [])
        assert result.total_samples == 0
        assert result.accuracy == 0.0

    def test_build_prompt(self):
        benchmark = MMLUBenchmark()
        sample = {'question': 'What is 2+2?', 'choices': ['A. 3', 'B. 4', 'C. 5', 'D. 6']}
        prompt = benchmark._build_prompt(sample)
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert 'What is 2+2?' in prompt

    def test_parse_answer_single_letter(self):
        benchmark = MMLUBenchmark()
        response = 'The answer is A.'
        answer = benchmark._parse_answer(response)
        assert answer == 'A'

    def test_parse_answer_multiple_letters(self):
        benchmark = MMLUBenchmark()
        response = 'The answer is B.'
        answer = benchmark._parse_answer(response)
        assert answer == 'B'

    def test_parse_answer_no_letter(self):
        benchmark = MMLUBenchmark()
        response = 'No answer provided.'
        answer = benchmark._parse_answer(response)
        assert answer in ['', 'A', 'B', 'C', 'D']

    def test_load_dataset_cache(self):
        benchmark = MMLUBenchmark()
        dataset1 = benchmark.load_dataset()
        dataset2 = benchmark.load_dataset()
        assert dataset1 is dataset2

    def test_generate_synthetic_data(self):
        benchmark = MMLUBenchmark()
        data = benchmark._generate_synthetic_data()
        assert len(data) == 100
        assert 'question' in data[0]
        assert 'choices' in data[0]
        assert 'answer' in data[0]
        assert 'subject' in data[0]

    def test_subjects_count(self):
        assert len(MMLUBenchmark.SUBJECTS) == 58

    def test_class_attributes(self):
        assert MMLUBenchmark.name == 'MMLU'
        assert MMLUBenchmark.category == 'knowledge'
        assert MMLUBenchmark.num_samples == 100

    def test_evaluate_with_error(self):
        benchmark = MMLUBenchmark()
        mock_client = MockLLMClient(['A'])
        samples = [
            {'question': 'Test', 'choices': ['A. X'], 'answer': 'A', 'id': 0, 'subject': 'test'},
        ]
        result = benchmark.evaluate(mock_client, samples)
        assert len(result.scores) == 1

    def test_empty_choices(self):
        benchmark = MMLUBenchmark()
        sample = {'question': 'Test', 'choices': [], 'answer': 'A', 'id': 0, 'subject': 'test'}
        prompt = benchmark._build_prompt(sample)
        assert isinstance(prompt, str)
