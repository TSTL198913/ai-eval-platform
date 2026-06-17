import pytest

from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.risk.risk_response import RiskResponseStrategy, RiskLevel
from src.schemas.evaluation import EvaluationSchema


class TestRiskEvaluator:
    def setup_method(self):
        self.evaluator = EvaluatorFactory.get("risk")

    def test_detect_all_risk(self):
        request = EvaluationSchema(
            id="risk_test_001",
            type="risk",
            payload={
                "action": "detect_all",
                "feature_complexity": 0.3,
                "core_alignment": 0.9,
                "responsibility_blur": 0.1,
                "unresolved_warnings": 10,
                "duplicate_code_ratio": 0.2,
                "pending_refactoring": 2,
                "documentation_gap": 0.1,
                "external_dependencies": 3,
                "cyclic_dependencies": 0,
                "cross_layer_calls": 0,
                "overall_coverage": 0.85,
                "new_code_coverage": 0.8,
                "critical_path_coverage": 0.9,
                "test_pass_rate": 0.95,
                "baseline_score": 0.9,
                "current_score": 0.88,
                "format_changes": 1,
                "latency_increase": 5,
                "error_rate_change": 0.02,
            },
        )
        result = self.evaluator.evaluate(request)
        assert result.is_valid is True
        assert "风险评估完成" in result.text
        assert result.score >= 0.5

    def test_detect_feature_creep_high_risk(self):
        request = EvaluationSchema(
            id="risk_test_002",
            type="risk",
            payload={
                "action": "feature_creep",
                "feature_complexity": 0.9,
                "core_alignment": 0.3,
                "responsibility_blur": 0.8,
            },
        )
        result = self.evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.data["risk_type"] == "feature_creep"
        assert result.data["risk_level"] == "high"

    def test_detect_feature_creep_low_risk(self):
        request = EvaluationSchema(
            id="risk_test_003",
            type="risk",
            payload={
                "action": "feature_creep",
                "feature_complexity": 0.1,
                "core_alignment": 0.95,
                "responsibility_blur": 0.05,
            },
        )
        result = self.evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.data["risk_level"] == "low"

    def test_detect_tech_debt(self):
        request = EvaluationSchema(
            id="risk_test_004",
            type="risk",
            payload={
                "action": "tech_debt",
                "unresolved_warnings": 50,
                "duplicate_code_ratio": 0.4,
                "pending_refactoring": 5,
                "documentation_gap": 0.3,
            },
        )
        result = self.evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.data["risk_type"] == "tech_debt"

    def test_detect_coupling(self):
        request = EvaluationSchema(
            id="risk_test_005",
            type="risk",
            payload={
                "action": "coupling",
                "external_dependencies": 8,
                "cyclic_dependencies": 1,
                "cross_layer_calls": 2,
            },
        )
        result = self.evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.data["risk_type"] == "coupling"

    def test_detect_test_coverage(self):
        request = EvaluationSchema(
            id="risk_test_006",
            type="risk",
            payload={
                "action": "test_coverage",
                "overall_coverage": 0.65,
                "new_code_coverage": 0.7,
                "critical_path_coverage": 0.75,
                "test_pass_rate": 0.9,
            },
        )
        result = self.evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.data["risk_type"] == "test_coverage"

    def test_detect_drift(self):
        request = EvaluationSchema(
            id="risk_test_007",
            type="risk",
            payload={
                "action": "drift",
                "baseline_score": 0.9,
                "current_score": 0.7,
                "format_changes": 5,
                "latency_increase": 30,
                "error_rate_change": 0.08,
            },
        )
        result = self.evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.data["risk_type"] == "drift"

    def test_unknown_action(self):
        request = EvaluationSchema(
            id="risk_test_008",
            type="risk",
            payload={"action": "unknown_action"},
        )
        result = self.evaluator.evaluate(request)
        assert result.is_valid is False
        assert "Unknown risk detection action" in result.error


class TestRiskResponseStrategy:
    def test_respond_feature_creep_high(self):
        response = RiskResponseStrategy.respond("feature_creep", RiskLevel.HIGH, {})
        assert response["action"] == "block"

    def test_respond_feature_creep_medium(self):
        response = RiskResponseStrategy.respond("feature_creep", RiskLevel.MEDIUM, {})
        assert response["action"] == "warn"

    def test_respond_feature_creep_low(self):
        response = RiskResponseStrategy.respond("feature_creep", RiskLevel.LOW, {})
        assert response["action"] == "pass"

    def test_respond_tech_debt(self):
        response = RiskResponseStrategy.respond("tech_debt", RiskLevel.HIGH, {})
        assert response["action"] == "block"

    def test_respond_coupling(self):
        response = RiskResponseStrategy.respond("coupling", RiskLevel.MEDIUM, {})
        assert response["action"] == "warn"

    def test_respond_test_coverage(self):
        response = RiskResponseStrategy.respond("test_coverage", RiskLevel.LOW, {})
        assert response["action"] == "pass"

    def test_respond_drift(self):
        response = RiskResponseStrategy.respond("drift", RiskLevel.HIGH, {})
        assert response["action"] == "block"

    def test_respond_unknown(self):
        response = RiskResponseStrategy.respond("unknown", RiskLevel.HIGH, {})
        assert response["action"] == "block"

    def test_evaluate_all(self):
        risk_results = {
            "details": {
                "feature_creep": {"risk_level": "high"},
                "tech_debt": {"risk_level": "medium"},
                "coupling": {"risk_level": "low"},
            }
        }
        result = RiskResponseStrategy.evaluate_all(risk_results)
        assert result["overall_action"] == "block"
        assert result["high_risk_count"] == 1
        assert result["medium_risk_count"] == 1
