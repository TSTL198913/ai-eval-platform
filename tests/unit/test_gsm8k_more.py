import pytest
from unittest.mock import MagicMock

from src.domain.benchmarks.gsm8k import GSM8KBenchmark


class TestGSM8KBenchmarkMore:
    def test_evaluate_with_mixed_results(self):
        benchmark = GSM8KBenchmark()
        mock_client = MagicMock()
        mock_client.chat_completion.side_effect = ['The answer is 4', 'The answer is 10', 'The answer is 8']
        samples = [
            {'question': '2+2', 'answer': '4', 'id': 0},
            {'question': '3+3', 'answer': '6', 'id': 1},
            {'question': '5+3', 'answer': '8', 'id': 2},
        ]
        result = benchmark.evaluate(mock_client, samples)
        assert result.correct_samples == 2
        assert result.accuracy == 2/3

    def test_evaluate_with_none_answer(self):
        benchmark = GSM8KBenchmark()
        mock_client = MagicMock()
        mock_client.chat_completion.return_value = 'No answer'
        samples = [
            {'question': '2+2', 'answer': '4', 'id': 0},
        ]
        result = benchmark.evaluate(mock_client, samples)
        assert result.correct_samples == 0

    def test_evaluate_with_empty_question(self):
        benchmark = GSM8KBenchmark()
        mock_client = MagicMock()
        mock_client.chat_completion.return_value = '0'
        samples = [
            {'question': '', 'answer': '0', 'id': 0},
        ]
        result = benchmark.evaluate(mock_client, samples)
        assert result.total_samples == 1

    def test_parse_answer_with_negative_number(self):
        benchmark = GSM8KBenchmark()
        response = 'The answer is -42.'
        answer = benchmark._parse_answer(response)
        assert '-42' in answer

    def test_parse_answer_with_decimal(self):
        benchmark = GSM8KBenchmark()
        response = 'The answer is 3.14.'
        answer = benchmark._parse_answer(response)
        assert '3.14' in answer

    def test_compare_answers_with_decimals(self):
        benchmark = GSM8KBenchmark()
        result = benchmark._compare_answers('3.14', '3.14159')
        assert result is True

    def test_compare_answers_integer_mismatch(self):
        benchmark = GSM8KBenchmark()
        result = benchmark._compare_answers('42', '43')
        assert result is False

    def test_compare_answers_string_fallback(self):
        benchmark = GSM8KBenchmark()
        result = benchmark._compare_answers('test', 'test')
        assert result is True

    def test_compare_answers_string_mismatch(self):
        benchmark = GSM8KBenchmark()
        result = benchmark._compare_answers('test1', 'test2')
        assert result is False

    def test_benchmark_class_attributes(self):
        assert GSM8KBenchmark.name == 'GSM8K'
        assert GSM8KBenchmark.category == 'reasoning'
        assert GSM8KBenchmark.num_samples == 50
