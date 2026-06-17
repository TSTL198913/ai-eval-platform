import pytest
from unittest.mock import MagicMock

from src.domain.benchmarks.mmlu import MMLUBenchmark


class TestMMLUBenchmarkMore:
    def test_evaluate_with_mixed_results(self):
        benchmark = MMLUBenchmark()
        mock_client = MagicMock()
        mock_client.chat_completion.side_effect = ['A', 'C', 'B']
        samples = [
            {'question': 'Q1', 'choices': ['A. X', 'B. Y'], 'answer': 'A', 'id': 0, 'subject': 'test'},
            {'question': 'Q2', 'choices': ['A. X', 'B. Y'], 'answer': 'B', 'id': 1, 'subject': 'test'},
            {'question': 'Q3', 'choices': ['A. X', 'B. Y'], 'answer': 'B', 'id': 2, 'subject': 'test'},
        ]
        result = benchmark.evaluate(mock_client, samples)
        assert result.correct_samples == 2

    def test_evaluate_with_none_answer(self):
        benchmark = MMLUBenchmark()
        mock_client = MagicMock()
        mock_client.chat_completion.return_value = 'No answer'
        samples = [
            {'question': 'Q1', 'choices': ['A. X', 'B. Y'], 'answer': 'A', 'id': 0, 'subject': 'test'},
        ]
        result = benchmark.evaluate(mock_client, samples)
        assert result.total_samples == 1

    def test_parse_answer_first_letter(self):
        benchmark = MMLUBenchmark()
        response = 'A'
        answer = benchmark._parse_answer(response)
        assert answer == 'A'

    def test_parse_answer_last_letter(self):
        benchmark = MMLUBenchmark()
        response = 'B A C D'
        answer = benchmark._parse_answer(response)
        assert answer == 'D'

    def test_parse_answer_lowercase(self):
        benchmark = MMLUBenchmark()
        response = 'the answer is b'
        answer = benchmark._parse_answer(response)
        assert answer == 'B'

    def test_build_prompt_with_long_choices(self):
        benchmark = MMLUBenchmark()
        sample = {
            'question': 'What is the capital?',
            'choices': ['A. London', 'B. Paris', 'C. Berlin', 'D. Rome']
        }
        prompt = benchmark._build_prompt(sample)
        assert len(prompt) > 0
        assert 'London' in prompt
        assert 'Paris' in prompt

    def test_build_prompt_with_no_choices(self):
        benchmark = MMLUBenchmark()
        sample = {'question': 'Test', 'choices': []}
        prompt = benchmark._build_prompt(sample)
        assert isinstance(prompt, str)

    def test_calculate_score_empty(self):
        benchmark = MMLUBenchmark()
        score = benchmark.calculate_score([])
        assert score == 0.0

    def test_calculate_score_with_results(self):
        benchmark = MMLUBenchmark()
        results = [{'is_correct': True}, {'is_correct': False}, {'is_correct': True}]
        score = benchmark.calculate_score(results)
        assert score == 2/3

    def test_synthetic_data_unique_ids(self):
        benchmark = MMLUBenchmark()
        data = benchmark._generate_synthetic_data()
        ids = [item['id'] for item in data]
        assert len(ids) == len(set(ids))
