import pytest
from unittest.mock import MagicMock, patch

from src.domain.online.evaluator import (
    OnlineEvaluator,
    ProductionSampler,
    SampledRequest,
    OnlineEvaluationResult,
    OnlineEvaluationStats,
)


class TestSampledRequest:
    def test_initialization(self):
        request = SampledRequest(request_id='1', user_input='test', model_output='output')
        assert request.request_id == '1'
        assert request.user_input == 'test'
        assert request.model_output == 'output'


class TestOnlineEvaluationResult:
    def test_initialization(self):
        result = OnlineEvaluationResult(request_id='1', is_success=True, score=0.8)
        assert result.request_id == '1'
        assert result.is_success is True
        assert result.score == 0.8


class TestOnlineEvaluationStats:
    def test_initialization(self):
        stats = OnlineEvaluationStats()
        assert stats.total_samples == 0
        assert stats.success_count == 0
        assert stats.failure_count == 0

    def test_success_rate(self):
        stats = OnlineEvaluationStats()
        stats.total_samples = 10
        stats.success_count = 8
        assert stats.success_rate == 0.8

    def test_to_dict(self):
        stats = OnlineEvaluationStats()
        stats_dict = stats.to_dict()
        assert 'total_samples' in stats_dict
        assert 'success_rate' in stats_dict


class TestProductionSampler:
    def test_initialization(self):
        sampler = ProductionSampler(sample_rate=0.5)
        assert sampler.sample_rate == 0.5

    def test_sample(self):
        sampler = ProductionSampler(sample_rate=1.0)
        request = sampler.sample('1', 'input', 'output')
        assert request is not None
        assert request.request_id == '1'

    def test_should_sample(self):
        sampler = ProductionSampler(sample_rate=1.0)
        assert sampler.should_sample() is True

    def test_get_sampled_requests(self):
        sampler = ProductionSampler(sample_rate=1.0)
        sampler.sample('1', 'input1', 'output1')
        sampler.sample('2', 'input2', 'output2')
        requests = sampler.get_sampled_requests()
        assert len(requests) == 2

    def test_clear(self):
        sampler = ProductionSampler(sample_rate=1.0)
        sampler.sample('1', 'input', 'output')
        sampler.clear()
        requests = sampler.get_sampled_requests()
        assert len(requests) == 0


class TestOnlineEvaluator:
    def test_initialization(self):
        mock_judge = MagicMock(return_value=(True, 0.8, 'good'))
        evaluator = OnlineEvaluator(mock_judge)
        assert evaluator is not None

    def test_evaluate(self):
        mock_judge = MagicMock(return_value=(True, 0.8, 'good'))
        evaluator = OnlineEvaluator(mock_judge)
        request = SampledRequest(request_id='1', user_input='test', model_output='output')
        result = evaluator.evaluate(request)
        assert result is not None
        assert result.is_success is True
        assert result.score == 0.8

    def test_evaluate_failure(self):
        mock_judge = MagicMock(return_value=(False, 0.2, 'bad'))
        evaluator = OnlineEvaluator(mock_judge)
        request = SampledRequest(request_id='1', user_input='test', model_output='output')
        result = evaluator.evaluate(request)
        assert result.is_success is False
        assert result.score == 0.2

    def test_evaluate_batch(self):
        mock_judge = MagicMock(return_value=(True, 0.8, 'good'))
        evaluator = OnlineEvaluator(mock_judge)
        requests = [
            SampledRequest(request_id='1', user_input='test1', model_output='output1'),
            SampledRequest(request_id='2', user_input='test2', model_output='output2'),
        ]
        results = evaluator.evaluate_batch(requests)
        assert len(results) == 2

    def test_classify_error_hallucination(self):
        mock_judge = MagicMock(return_value=(False, 0.2, 'hallucination detected'))
        evaluator = OnlineEvaluator(mock_judge)
        request = SampledRequest(request_id='1', user_input='test', model_output='output')
        result = evaluator.evaluate(request)
        assert result.error_type == 'hallucination'

    def test_classify_error_format(self):
        mock_judge = MagicMock(return_value=(False, 0.2, 'format error'))
        evaluator = OnlineEvaluator(mock_judge)
        request = SampledRequest(request_id='1', user_input='test', model_output='output')
        result = evaluator.evaluate(request)
        assert result.error_type == 'format_error'

    def test_recycle_failed_samples_no_manager(self):
        mock_judge = MagicMock()
        evaluator = OnlineEvaluator(mock_judge)
        results = evaluator.recycle_failed_samples('dataset1')
        assert len(results) == 0

    def test_recycle_failed_samples_with_manager(self):
        mock_judge = MagicMock(return_value=(False, 0.2, 'bad'))
        mock_manager = MagicMock()
        evaluator = OnlineEvaluator(mock_judge, dataset_manager=mock_manager)
        request = SampledRequest(request_id='1', user_input='test', model_output='output')
        evaluator.evaluate(request)
        results = evaluator.recycle_failed_samples('dataset1')
        assert len(results) == 1
