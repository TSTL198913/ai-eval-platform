"""Risk metrics tests"""

from src.infra.monitoring.risk_metrics import (
    FEATURE_CREEP_RISK, TECH_DEBT_RISK, COUPLING_RISK, TEST_COVERAGE_RISK,
    DRIFT_RISK, RISK_EVENTS, record_risk_metrics, check_risk_thresholds,
)

class TestRiskMetrics:
    def test_record_feature_creep(self):
        FEATURE_CREEP_RISK.clear()
        RISK_EVENTS.clear()
        record_risk_metrics({"details": {"feature_creep": {"risk_score": 0.8, "risk_level": "high", "metrics": {"module": "test"}}}})
        assert FEATURE_CREEP_RISK.labels(module="test")._value.get() == 0.8

    def test_record_tech_debt(self):
        TECH_DEBT_RISK.clear()
        RISK_EVENTS.clear()
        record_risk_metrics({"details": {"tech_debt": {"risk_score": 0.6, "risk_level": "medium", "metrics": {"module": "test"}}}})
        assert TECH_DEBT_RISK.labels(module="test")._value.get() == 0.6

    def test_record_coupling(self):
        COUPLING_RISK.clear()
        RISK_EVENTS.clear()
        record_risk_metrics({"details": {"coupling": {"risk_score": 0.5, "risk_level": "medium", "metrics": {"module": "test"}}}})
        assert COUPLING_RISK.labels(module="test")._value.get() == 0.5

    def test_record_test_coverage(self):
        TEST_COVERAGE_RISK.clear()
        RISK_EVENTS.clear()
        record_risk_metrics({"details": {"test_coverage": {"risk_score": 0.3, "risk_level": "low", "metrics": {"module": "test"}}}})
        assert TEST_COVERAGE_RISK.labels(module="test")._value.get() == 0.3

    def test_record_drift(self):
        DRIFT_RISK.clear()
        RISK_EVENTS.clear()
        record_risk_metrics({"details": {"drift": {"risk_score": 0.9, "risk_level": "critical", "metrics": {"module": "finance"}}}})
        assert DRIFT_RISK.labels(evaluator_type="finance")._value.get() == 0.9

    def test_record_empty(self):
        record_risk_metrics({})

    def test_record_no_details(self):
        record_risk_metrics({"details": None})

    def test_check_feature_creep_threshold(self):
        FEATURE_CREEP_RISK.clear()
        TECH_DEBT_RISK.clear()
        COUPLING_RISK.clear()
        FEATURE_CREEP_RISK.labels(module="high").set(0.8)
        warnings = check_risk_thresholds()
        assert len(warnings) == 1

    def test_check_tech_debt_threshold(self):
        FEATURE_CREEP_RISK.clear()
        TECH_DEBT_RISK.clear()
        COUPLING_RISK.clear()
        TECH_DEBT_RISK.labels(module="debt").set(0.7)
        warnings = check_risk_thresholds()
        assert any(w["type"] == "tech_debt" for w in warnings)

    def test_check_coupling_threshold(self):
        FEATURE_CREEP_RISK.clear()
        TECH_DEBT_RISK.clear()
        COUPLING_RISK.clear()
        COUPLING_RISK.labels(module="coupled").set(0.6)
        warnings = check_risk_thresholds()
        assert any(w["type"] == "coupling" for w in warnings)

    def test_check_no_threshold_breach(self):
        FEATURE_CREEP_RISK.clear()
        TECH_DEBT_RISK.clear()
        COUPLING_RISK.clear()
        FEATURE_CREEP_RISK.labels(module="safe").set(0.5)
        TECH_DEBT_RISK.labels(module="safe").set(0.4)
        COUPLING_RISK.labels(module="safe").set(0.3)
        warnings = check_risk_thresholds()
        assert len(warnings) == 0

    def test_check_empty_metrics(self):
        FEATURE_CREEP_RISK.clear()
        TECH_DEBT_RISK.clear()
        COUPLING_RISK.clear()
        warnings = check_risk_thresholds()
        assert len(warnings) == 0
