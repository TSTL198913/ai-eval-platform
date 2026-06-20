
from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.schemas.evaluation import DomainResponse, EvaluationSchema


@EvaluatorFactory.register("risk")
class RiskEvaluator(BaseEvaluator):
    """迭代优化风险评估器

    检测并评估以下风险：
    - 功能蔓延风险
    - 技术债务累积风险
    - 模块耦合风险
    - 测试覆盖不足风险
    - 行为漂移风险
    """

    RISK_THRESHOLDS = {
        "feature_creep": 0.7,
        "tech_debt": 0.6,
        "coupling": 0.5,
        "test_coverage": 0.8,
        "drift": 0.2,
    }

    def evaluate(self, request: EvaluationSchema) -> DomainResponse:
        action = self.get_payload_data(request, "action", "detect_all")

        if action == "detect_all":
            return self._detect_all_risk(request)
        elif action == "feature_creep":
            return self._detect_feature_creep(request)
        elif action == "tech_debt":
            return self._detect_tech_debt(request)
        elif action == "coupling":
            return self._detect_coupling(request)
        elif action == "test_coverage":
            return self._detect_test_coverage(request)
        elif action == "drift":
            return self._detect_drift(request)
        else:
            return DomainResponse(
                is_valid=False,
                error=f"Unknown risk detection action: {action}",
            )

    def _detect_all_risk(self, request: EvaluationSchema) -> DomainResponse:
        feature_creep_result = self._detect_feature_creep(request)
        tech_debt_result = self._detect_tech_debt(request)
        coupling_result = self._detect_coupling(request)
        test_coverage_result = self._detect_test_coverage(request)
        drift_result = self._detect_drift(request)

        risks = [
            ("feature_creep", feature_creep_result),
            ("tech_debt", tech_debt_result),
            ("coupling", coupling_result),
            ("test_coverage", test_coverage_result),
            ("drift", drift_result),
        ]

        high_risks = [name for name, result in risks if result.data.get("risk_level") == "high"]
        medium_risks = [name for name, result in risks if result.data.get("risk_level") == "medium"]

        overall_risk_level = "low"
        if high_risks:
            overall_risk_level = "high"
        elif medium_risks:
            overall_risk_level = "medium"

        return DomainResponse(
            is_valid=True,
            text=f"风险评估完成，检测到 {len(high_risks)} 个高风险，{len(medium_risks)} 个中风险",
            score=1.0 if overall_risk_level == "low" else (0.5 if overall_risk_level == "medium" else 0.0),
            data={
                "overall_risk_level": overall_risk_level,
                "high_risks": high_risks,
                "medium_risks": medium_risks,
                "details": {
                    "feature_creep": feature_creep_result.data,
                    "tech_debt": tech_debt_result.data,
                    "coupling": coupling_result.data,
                    "test_coverage": test_coverage_result.data,
                    "drift": drift_result.data,
                },
            },
        )

    def _detect_feature_creep(self, request: EvaluationSchema) -> DomainResponse:
        feature_complexity = self.get_payload_data(request, "feature_complexity", 0)
        core_alignment = self.get_payload_data(request, "core_alignment", 1.0)
        responsibility_blur = self.get_payload_data(request, "responsibility_blur", 0)

        risk_score = (1 - core_alignment) * 0.5 + feature_complexity * 0.3 + responsibility_blur * 0.2

        risk_level = self._get_risk_level(risk_score, self.RISK_THRESHOLDS["feature_creep"])

        return DomainResponse(
            is_valid=True,
            text=f"功能蔓延风险评估完成，风险等级: {risk_level}",
            score=1.0 - risk_score,
            data={
                "risk_type": "feature_creep",
                "risk_level": risk_level,
                "risk_score": risk_score,
                "metrics": {
                    "feature_complexity": feature_complexity,
                    "core_alignment": core_alignment,
                    "responsibility_blur": responsibility_blur,
                },
                "suggestion": "建议审查新增功能是否符合核心目标，考虑拆分或延期非核心功能" if risk_level in ("medium", "high") else "功能范围控制良好",
            },
        )

    def _detect_tech_debt(self, request: EvaluationSchema) -> DomainResponse:
        unresolved_warnings = self.get_payload_data(request, "unresolved_warnings", 0)
        duplicate_code_ratio = self.get_payload_data(request, "duplicate_code_ratio", 0)
        pending_refactoring = self.get_payload_data(request, "pending_refactoring", 0)
        documentation_gap = self.get_payload_data(request, "documentation_gap", 0)

        risk_score = (
            min(unresolved_warnings / 100, 1) * 0.3
            + duplicate_code_ratio * 0.3
            + min(pending_refactoring / 10, 1) * 0.2
            + documentation_gap * 0.2
        )

        risk_level = self._get_risk_level(risk_score, self.RISK_THRESHOLDS["tech_debt"])

        return DomainResponse(
            is_valid=True,
            text=f"技术债务风险评估完成，风险等级: {risk_level}",
            score=1.0 - risk_score,
            data={
                "risk_type": "tech_debt",
                "risk_level": risk_level,
                "risk_score": risk_score,
                "metrics": {
                    "unresolved_warnings": unresolved_warnings,
                    "duplicate_code_ratio": duplicate_code_ratio,
                    "pending_refactoring": pending_refactoring,
                    "documentation_gap": documentation_gap,
                },
                "suggestion": "建议优先清理技术债务，制定定期清理计划" if risk_level in ("medium", "high") else "技术债务控制良好",
            },
        )

    def _detect_coupling(self, request: EvaluationSchema) -> DomainResponse:
        external_dependencies = self.get_payload_data(request, "external_dependencies", 0)
        cyclic_dependencies = self.get_payload_data(request, "cyclic_dependencies", 0)
        cross_layer_calls = self.get_payload_data(request, "cross_layer_calls", 0)

        risk_score = (
            min(external_dependencies / 10, 1) * 0.5
            + cyclic_dependencies * 0.3
            + cross_layer_calls * 0.2
        )

        risk_level = self._get_risk_level(risk_score, self.RISK_THRESHOLDS["coupling"])

        return DomainResponse(
            is_valid=True,
            text=f"模块耦合风险评估完成，风险等级: {risk_level}",
            score=1.0 - risk_score,
            data={
                "risk_type": "coupling",
                "risk_level": risk_level,
                "risk_score": risk_score,
                "metrics": {
                    "external_dependencies": external_dependencies,
                    "cyclic_dependencies": cyclic_dependencies,
                    "cross_layer_calls": cross_layer_calls,
                },
                "suggestion": "建议减少跨层调用，考虑引入中间层解耦" if risk_level in ("medium", "high") else "模块耦合度控制良好",
            },
        )

    def _detect_test_coverage(self, request: EvaluationSchema) -> DomainResponse:
        overall_coverage = self.get_payload_data(request, "overall_coverage", 0)
        new_code_coverage = self.get_payload_data(request, "new_code_coverage", 0)
        critical_path_coverage = self.get_payload_data(request, "critical_path_coverage", 0)
        test_pass_rate = self.get_payload_data(request, "test_pass_rate", 1.0)

        risk_score = (
            max(0, self.RISK_THRESHOLDS["test_coverage"] - overall_coverage) * 0.25
            + max(0, self.RISK_THRESHOLDS["test_coverage"] - new_code_coverage) * 0.35
            + max(0, self.RISK_THRESHOLDS["test_coverage"] - critical_path_coverage) * 0.25
            + (1 - test_pass_rate) * 0.15
        )

        risk_level = "low"
        if risk_score >= 0.5:
            risk_level = "high"
        elif risk_score >= 0.25:
            risk_level = "medium"

        return DomainResponse(
            is_valid=True,
            text=f"测试覆盖风险评估完成，风险等级: {risk_level}",
            score=1.0 - risk_score,
            data={
                "risk_type": "test_coverage",
                "risk_level": risk_level,
                "risk_score": risk_score,
                "metrics": {
                    "overall_coverage": overall_coverage,
                    "new_code_coverage": new_code_coverage,
                    "critical_path_coverage": critical_path_coverage,
                    "test_pass_rate": test_pass_rate,
                },
                "suggestion": "建议补充测试用例，重点覆盖新增代码和关键路径" if risk_level in ("medium", "high") else "测试覆盖率良好",
            },
        )

    def _detect_drift(self, request: EvaluationSchema) -> DomainResponse:
        baseline_score = self.get_payload_data(request, "baseline_score", 0)
        current_score = self.get_payload_data(request, "current_score", 0)
        format_changes = self.get_payload_data(request, "format_changes", 0)
        latency_increase = self.get_payload_data(request, "latency_increase", 0)
        error_rate_change = self.get_payload_data(request, "error_rate_change", 0)

        score_drift = abs(baseline_score - current_score)
        risk_score = (
            score_drift * 0.4
            + min(format_changes / 10, 1) * 0.25
            + min(latency_increase / 100, 1) * 0.2
            + min(error_rate_change / 0.1, 1) * 0.15
        )

        risk_level = self._get_risk_level(risk_score, self.RISK_THRESHOLDS["drift"])

        return DomainResponse(
            is_valid=True,
            text=f"行为漂移风险评估完成，风险等级: {risk_level}",
            score=1.0 - risk_score,
            data={
                "risk_type": "drift",
                "risk_level": risk_level,
                "risk_score": risk_score,
                "metrics": {
                    "baseline_score": baseline_score,
                    "current_score": current_score,
                    "score_drift": score_drift,
                    "format_changes": format_changes,
                    "latency_increase": latency_increase,
                    "error_rate_change": error_rate_change,
                },
                "suggestion": "建议审查最近的代码变更，定位漂移原因并修复" if risk_level in ("medium", "high") else "系统行为稳定，无明显漂移",
            },
        )

    def _get_risk_level(self, risk_score: float, threshold: float) -> str:
        if risk_score >= threshold:
            return "high"
        elif risk_score >= threshold * 0.5:
            return "medium"
        else:
            return "low"
