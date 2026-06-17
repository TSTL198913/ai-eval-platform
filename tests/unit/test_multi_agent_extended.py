import pytest
from unittest.mock import MagicMock, patch

from src.domain.evaluators.multi_agent_evaluator import MultiAgentEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestMultiAgentEvaluator:
    def test_evaluate_basic(self):
        evaluator = MultiAgentEvaluator()
        request = EvaluationSchema(
            id='test',
            type='multi_agent',
            payload={
                'agent_outputs': [
                    {'agent_id': 'agent1', 'output': 'response1'},
                    {'agent_id': 'agent2', 'output': 'response2'}
                ]
            },
            metadata={}
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True

    def test_evaluate_single_agent(self):
        evaluator = MultiAgentEvaluator()
        request = EvaluationSchema(
            id='test',
            type='multi_agent',
            payload={
                'agent_outputs': [
                    {'agent_id': 'agent1', 'output': 'response1'}
                ]
            },
            metadata={}
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True

    def test_evaluate_empty_outputs(self):
        evaluator = MultiAgentEvaluator()
        request = EvaluationSchema(
            id='test',
            type='multi_agent',
            payload={'agent_outputs': []},
            metadata={}
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True

    def test_evaluate_with_conflict_detection(self):
        evaluator = MultiAgentEvaluator()
        request = EvaluationSchema(
            id='test',
            type='multi_agent',
            payload={
                'agent_outputs': [
                    {'agent_id': 'agent1', 'output': 'The answer is 42'},
                    {'agent_id': 'agent2', 'output': 'The answer is 100'}
                ],
                'detect_conflicts': True
            },
            metadata={}
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True

    def test_evaluate_with_metadata(self):
        evaluator = MultiAgentEvaluator()
        request = EvaluationSchema(
            id='test',
            type='multi_agent',
            payload={
                'agent_outputs': [
                    {'agent_id': 'agent1', 'output': 'response'}
                ]
            },
            metadata={'user_id': '123', 'session_id': 'sess1'}
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
