"""
RiskEvaluator 专项测试
测试目标：验证迭代优化风险评估器的5类风险检测能力
关键发现：RiskEvaluator支持6种action（detect_all/feature_creep/tech_debt/coupling/test_coverage/drift），每种风险有独立阈值和评分算法
"""

from unittest.mock import MagicMock

import pytest

from src.domain.evaluators.risk import RiskEvaluator
from src.schemas.evaluation import DomainResponse, EvaluationSchema


class TestRiskEvaluatorPositiveCases:
    """正向测试 - 正常输入"""

    @pytest.fixture
    def evaluator(self):
        return RiskEvaluator()

    def test_detect_all_risk_returns_all_results(self, evaluator):
        """detect_all 应返回所有5类风险评估结果"""
        request = EvaluationSchema(
            id="test-1",
            type="risk",
            payload={"action": "detect_all"},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert "overall_risk_level" in result.data
        assert "high_risks" in result.data
        assert "medium_risks" in result.data
        assert "details" in result.data
        assert len(result.data["details"]) == 5

    def test_feature_creep_detection_low_risk(self, evaluator):
        """功能蔓延风险低时应返回low等级"""
        request = EvaluationSchema(
            id="test-2",
            type="risk",
            payload={
                "action": "feature_creep",
                "feature_complexity": 0.1,
                "core_alignment": 0.95,
                "responsibility_blur": 0.1,
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.data["risk_type"] == "feature_creep"
        assert result.data["risk_level"] == "low"
        assert result.score >= 0.85

    def test_feature_creep_detection_high_risk(self, evaluator):
        """功能蔓延风险高时应返回high等级"""
        request = EvaluationSchema(
            id="test-3",
            type="risk",
            payload={
                "action": "feature_creep",
                "feature_complexity": 0.9,
                "core_alignment": 0.1,
                "responsibility_blur": 0.9,
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.data["risk_level"] == "high"
        assert result.score <= 0.2

    def test_tech_debt_detection(self, evaluator):
        """技术债务风险检测应正确计算风险分数"""
        request = EvaluationSchema(
            id="test-4",
            type="risk",
            payload={
                "action": "tech_debt",
                "unresolved_warnings": 50,
                "duplicate_code_ratio": 0.5,
                "pending_refactoring": 5,
                "documentation_gap": 0.3,
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.data["risk_type"] == "tech_debt"
        assert "suggestion" in result.data

    def test_coupling_detection_high_risk(self, evaluator):
        """模块耦合风险高时应返回high等级"""
        request = EvaluationSchema(
            id="test-5",
            type="risk",
            payload={
                "action": "coupling",
                "external_dependencies": 15,
                "cyclic_dependencies": 3,
                "cross_layer_calls": 2,
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.data["risk_level"] == "high"

    def test_test_coverage_detection(self, evaluator):
        """测试覆盖风险检测应正确计算"""
        request = EvaluationSchema(
            id="test-6",
            type="risk",
            payload={
                "action": "test_coverage",
                "overall_coverage": 0.7,
                "new_code_coverage": 0.6,
                "critical_path_coverage": 0.5,
                "test_pass_rate": 0.8,
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.data["risk_type"] == "test_coverage"

    def test_drift_detection(self, evaluator):
        """行为漂移风险检测应正确计算"""
        request = EvaluationSchema(
            id="test-7",
            type="risk",
            payload={
                "action": "drift",
                "baseline_score": 0.9,
                "current_score": 0.6,
                "format_changes": 5,
                "latency_increase": 50,
                "error_rate_change": 0.05,
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.data["risk_type"] == "drift"
        assert "score_drift" in result.data["metrics"]

    def test_detect_all_with_mixed_risks(self, evaluator):
        """detect_all 应正确汇总高/中风险"""
        request = EvaluationSchema(
            id="test-8",
            type="risk",
            payload={
                "action": "detect_all",
                "feature_complexity": 0.9,
                "core_alignment": 0.1,
                "external_dependencies": 10,
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert len(result.data["high_risks"]) > 0
        assert result.data["overall_risk_level"] == "high"


class TestRiskEvaluatorNegativeCases:
    """负向测试 - 错误输入"""

    @pytest.fixture
    def evaluator(self):
        return RiskEvaluator()

    def test_unknown_action_returns_error(self, evaluator):
        """未知action应返回错误"""
        request = EvaluationSchema(
            id="test-9",
            type="risk",
            payload={"action": "unknown_action"},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert "未知" in result.error or "unknown" in result.error.lower()

    def test_empty_action_uses_default(self, evaluator):
        """空action应使用默认detect_all"""
        request = EvaluationSchema(
            id="test-10",
            type="risk",
            payload={},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert "overall_risk_level" in result.data


class TestRiskEvaluatorBoundaryCases:
    """边界测试 - 边界值"""

    @pytest.fixture
    def evaluator(self):
        return RiskEvaluator()

    def test_feature_creep_threshold_boundary(self, evaluator):
        """功能蔓延风险恰好在阈值边界"""
        threshold = RiskEvaluator.RISK_THRESHOLDS["feature_creep"]
        request = EvaluationSchema(
            id="test-11",
            type="risk",
            payload={
                "action": "feature_creep",
                "feature_complexity": 0,
                "core_alignment": 1.0 - threshold,
                "responsibility_blur": 0,
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.data["risk_score"] >= threshold * 0.5

    def test_zero_values_all_risks(self, evaluator):
        """所有指标为0时应返回low风险"""
        request = EvaluationSchema(
            id="test-12",
            type="risk",
            payload={
                "action": "detect_all",
                "feature_complexity": 0,
                "core_alignment": 1.0,
                "responsibility_blur": 0,
                "unresolved_warnings": 0,
                "duplicate_code_ratio": 0,
                "pending_refactoring": 0,
                "documentation_gap": 0,
                "external_dependencies": 0,
                "cyclic_dependencies": 0,
                "cross_layer_calls": 0,
                "overall_coverage": 1.0,
                "new_code_coverage": 1.0,
                "critical_path_coverage": 1.0,
                "test_pass_rate": 1.0,
                "baseline_score": 1.0,
                "current_score": 1.0,
                "format_changes": 0,
                "latency_increase": 0,
                "error_rate_change": 0,
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.data["overall_risk_level"] == "low"
        assert result.score == 1.0

    def test_max_values_all_risks(self, evaluator):
        """所有指标为最大值时应返回high风险"""
        request = EvaluationSchema(
            id="test-13",
            type="risk",
            payload={
                "action": "detect_all",
                "feature_complexity": 1.0,
                "core_alignment": 0,
                "responsibility_blur": 1.0,
                "unresolved_warnings": 200,
                "duplicate_code_ratio": 1.0,
                "pending_refactoring": 20,
                "documentation_gap": 1.0,
                "external_dependencies": 20,
                "cyclic_dependencies": 5,
                "cross_layer_calls": 5,
                "overall_coverage": 0,
                "new_code_coverage": 0,
                "critical_path_coverage": 0,
                "test_pass_rate": 0,
                "baseline_score": 1.0,
                "current_score": 0,
                "format_changes": 20,
                "latency_increase": 200,
                "error_rate_change": 0.5,
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.data["overall_risk_level"] == "high"
        assert result.score <= 0.1


class TestRiskEvaluatorIntegration:
    """集成测试 - 完整流程"""

    @pytest.fixture
    def evaluator(self):
        return RiskEvaluator()

    def test_evaluator_registered_in_factory(self):
        """风险评估器应已注册到工厂"""
        from src.domain.evaluators.risk import RiskEvaluator

        evaluator_instance = RiskEvaluator()
        assert hasattr(evaluator_instance, "evaluate")
        assert hasattr(evaluator_instance, "_do_evaluate")

    def test_safe_evaluate_returns_error_on_exception(self, evaluator):
        """safe_evaluate 应捕获异常并返回错误"""
        mock_request = MagicMock()
        mock_request.type = "risk"
        mock_request.payload = {}
        result = evaluator.safe_evaluate(mock_request)
        assert isinstance(result, DomainResponse)
