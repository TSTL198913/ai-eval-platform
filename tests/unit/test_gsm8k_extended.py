import pytest
from unittest.mock import MagicMock

from src.domain.benchmarks.gsm8k import GSM8KBenchmark
from src.domain.benchmarks.base import BenchmarkResult


class MockLLMClient:
    def __init__(self, answers):
        self.answers = answers
        self.call_count = 0

    def chat_completion(self, prompt):
        self.call_count += 1
        idx = self.call_count - 1
        return self.answers[idx] if idx < len(self.answers) else 'A'


class TestGSM8KBenchmark:
    def test_evaluate_all_correct(self):
        benchmark = GSM8KBenchmark()
        mock_client = MockLLMClient(['The answer is 8', 'The answer is 180'])
        samples = [
            {'question': 'John has 5 apples. He buys 3 more. How many?', 'answer': '8', 'id': 0},
            {'question': 'A train travels at 60 mph for 3 hours. How far?', 'answer': '180', 'id': 1},
        ]
        result = benchmark.evaluate(mock_client, samples)
        assert result.total_samples == 2
        assert result.correct_samples == 2
        assert result.accuracy == 1.0

    def test_evaluate_all_wrong(self):
        benchmark = GSM8KBenchmark()
        mock_client = MockLLMClient(['The answer is 10', 'The answer is 200'])
        samples = [
            {'question': '2+2', 'answer': '4', 'id': 0},
            {'question': '3+3', 'answer': '6', 'id': 1},
        ]
        result = benchmark.evaluate(mock_client, samples)
        assert result.accuracy == 0.0

    def test_evaluate_partial_correct(self):
        benchmark = GSM8KBenchmark()
        mock_client = MockLLMClient(['The answer is 4', 'The answer is 10'])
        samples = [
            {'question': '2+2', 'answer': '4', 'id': 0},
            {'question': '3+3', 'answer': '6', 'id': 1},
        ]
        result = benchmark.evaluate(mock_client, samples)
        assert result.correct_samples == 1
        assert result.accuracy == 0.5

    def test_evaluate_empty_samples(self):
        benchmark = GSM8KBenchmark()
        mock_client = MockLLMClient([])
        result = benchmark.evaluate(mock_client, [])
        assert result.total_samples == 0
        assert result.accuracy == 0.0

    def test_evaluate_with_error(self):
        benchmark = GSM8KBenchmark()
        mock_client = MockLLMClient(['The answer is 4'])
        samples = [
            {'question': '2+2', 'answer': '4', 'id': 0},
        ]
        result = benchmark.evaluate(mock_client, samples)
        assert len(result.scores) == 1

    def test_build_prompt(self):
        benchmark = GSM8KBenchmark()
        sample = {'question': 'What is 2+2?'}
        prompt = benchmark._build_prompt(sample)
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert '2+2' in prompt

    def test_parse_answer_with_number(self):
        benchmark = GSM8KBenchmark()
        response = 'The answer is 42.'
        answer = benchmark._parse_answer(response)
        assert '42' in answer

    def test_parse_answer_without_number(self):
        benchmark = GSM8KBenchmark()
        response = 'I dont know the answer.'
        answer = benchmark._parse_answer(response)
        assert answer == ''

    def test_parse_answer_multiple_numbers(self):
        benchmark = GSM8KBenchmark()
        response = 'First 10, then 20, finally 30.'
        answer = benchmark._parse_answer(response)
        assert '30' in answer

    def test_compare_answers_exact_match(self):
        benchmark = GSM8KBenchmark()
        result = benchmark._compare_answers('42', '42')
        assert result is True

    def test_compare_answers_different(self):
        benchmark = GSM8KBenchmark()
        result = benchmark._compare_answers('42', '43')
        assert result is False

    def test_compare_answers_with_extra_text(self):
        benchmark = GSM8KBenchmark()
        result = benchmark._compare_answers('42.0', '42')
        assert result is True

    def test_compare_answers_empty(self):
        benchmark = GSM8KBenchmark()
        result = benchmark._compare_answers('', '42')
        assert result is False

    def test_load_dataset_cache(self):
        benchmark = GSM8KBenchmark()
        dataset1 = benchmark.load_dataset()
        dataset2 = benchmark.load_dataset()
        assert dataset1 is dataset2

    def test_generate_synthetic_data(self):
        benchmark = GSM8KBenchmark()
        data = benchmark._generate_synthetic_data()
        assert len(data) == 50
        assert 'question' in data[0]
        assert 'answer' in data[0]
