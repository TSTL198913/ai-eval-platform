import pytest
from unittest.mock import MagicMock, patch

from src.domain.evaluators.risk import RiskEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestRiskEvaluator:
    def test_evaluate_detect_all(self):
        evaluator = RiskEvaluator()
        request = EvaluationSchema(
            id='test',
            type='risk',
            payload={'action': 'detect_all'},
            metadata={}
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True

    def test_evaluate_feature_creep(self):
        evaluator = RiskEvaluator()
        request = EvaluationSchema(
            id='test',
            type='risk',
            payload={'action': 'feature_creep'},
            metadata={}
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True

    def test_evaluate_tech_debt(self):
        evaluator = RiskEvaluator()
        request = EvaluationSchema(
            id='test',
            type='risk',
            payload={'action': 'tech_debt'},
            metadata={}
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True

    def test_evaluate_coupling(self):
        evaluator = RiskEvaluator()
        request = EvaluationSchema(
            id='test',
            type='risk',
            payload={'action': 'coupling'},
            metadata={}
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True

    def test_evaluate_test_coverage(self):
        evaluator = RiskEvaluator()
        request = EvaluationSchema(
            id='test',
            type='risk',
            payload={'action': 'test_coverage'},
            metadata={}
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True

    def test_evaluate_drift(self):
        evaluator = RiskEvaluator()
        request = EvaluationSchema(
            id='test',
            type='risk',
            payload={'action': 'drift'},
            metadata={}
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True

    def test_evaluate_unknown_action(self):
        evaluator = RiskEvaluator()
        request = EvaluationSchema(
            id='test',
            type='risk',
            payload={'action': 'unknown'},
            metadata={}
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False

    def test_evaluate_default_action(self):
        evaluator = RiskEvaluator()
        request = EvaluationSchema(
            id='test',
            type='risk',
            payload={},
            metadata={}
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
