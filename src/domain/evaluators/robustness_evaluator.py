"""
Robustness Evaluator - 鲁棒性指数综合加权评估器

整合多维度评估，输出统一的鲁棒性指数(0-1)：
- 输入扰动鲁棒性
- 输出稳定性
- 错误恢复能力
- 异常处理能力
- 安全性（无注入/越狱触发）
"""
import statistics
from typing import Any

from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.schemas.evaluation import DomainResponse, EvaluationSchema


@EvaluatorFactory.register("robustness")
class RobustnessEvaluator:
    """鲁棒性指数评估器

    输入payload格式:
    {
        "action": "evaluate_robustness",
        "test_results": [
            {"input": "...", "output": "...", "expected": "...", "score": 0.9},
            ...
        ],
        "perturbation_results": [...],      # 扰动测试结果
        "security_results": {...},          # 安全测试结果
        "drift_results": {...},             # 漂移检测结果
        "weights": {...}                    # 自定义权重
    }
    """

    DEFAULT_WEIGHTS = {
        "consistency": 0.25,         # 输出一致性
        "perturbation_resistance": 0.20,  # 扰动抵抗
        "error_recovery": 0.15,       # 错误恢复
        "security": 0.20,            # 安全性
        "drift_resistance": 0.10,    # 漂移抵抗
        "stability": 0.10,           # 稳定性
    }

    def __init__(self, client: Any | None = None):
        self.client = client

    def evaluate(self, request: EvaluationSchema) -> DomainResponse:
        action = request.payload.get("action", "evaluate_robustness")
        handler = {
            "evaluate_robustness": self._evaluate_robustness,
            "perturbation_test": self._evaluate_perturbation,
            "stability_score": self._evaluate_stability,
            "error_recovery": self._evaluate_error_recovery,
        }.get(action)
        if handler is None:
            return DomainResponse(
                data={"is_valid": False, "error": f"Unknown action: {action}"},
                status_code=400,
            )
        try:
            return handler(request)
        except Exception as e:
            return DomainResponse(
                data={"is_valid": False, "error": str(e)},
                status_code=500,
            )

    def safe_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        return self.evaluate(request)

    # ===================== 核心评估方法 =====================

    def _evaluate_robustness(self, request: EvaluationSchema) -> DomainResponse:
        """综合鲁棒性指数计算"""
        test_results = self._get_payload(request, "test_results", [])
        perturbation_results = self._get_payload(request, "perturbation_results", [])
        security_results = self._get_payload(request, "security_results", {})
        drift_results = self._get_payload(request, "drift_results", {})
        weights = self._get_payload(request, "weights", self.DEFAULT_WEIGHTS)

        # 1. 输出一致性
        consistency = self._calc_consistency(test_results)
        # 2. 扰动抵抗
        perturbation = self._calc_perturbation_resistance(perturbation_results)
        # 3. 错误恢复
        error_recovery = self._calc_error_recovery(test_results)
        # 4. 安全性
        security = self._calc_security_score(security_results)
        # 5. 漂移抵抗
        drift_resistance = self._calc_drift_resistance(drift_results)
        # 6. 稳定性
        stability = self._calc_stability(test_results)

        # 综合评分
        scores = {
            "consistency": consistency,
            "perturbation_resistance": perturbation,
            "error_recovery": error_recovery,
            "security": security,
            "drift_resistance": drift_resistance,
            "stability": stability,
        }

        # 验证权重
        total_weight = sum(weights.values())
        if abs(total_weight - 1.0) > 0.01:
            # 归一化权重
            weights = {k: v / total_weight for k, v in weights.items()}

        robustness_index = sum(scores[k] * weights.get(k, 0) for k in scores)

        # 鲁棒性等级
        if robustness_index >= 0.9:
            level = "excellent"
        elif robustness_index >= 0.75:
            level = "good"
        elif robustness_index >= 0.6:
            level = "acceptable"
        elif robustness_index >= 0.4:
            level = "weak"
        else:
            level = "poor"

        return DomainResponse(
            data={
                "is_valid": True,
                "robustness_index": round(robustness_index, 4),
                "robustness_level": level,
                "dimension_scores": {k: round(v, 4) for k, v in scores.items()},
                "weights": weights,
                "recommendations": self._generate_recommendations(scores),
            },
            status_code=200,
        )

    def _evaluate_perturbation(self, request: EvaluationSchema) -> DomainResponse:
        """评估对扰动的抵抗能力"""
        perturbation_results = self._get_payload(request, "perturbation_results", [])

        score = self._calc_perturbation_resistance(perturbation_results)
        details = self._analyze_perturbations(perturbation_results)

        return DomainResponse(
            data={
                "is_valid": True,
                "perturbation_resistance_score": round(score, 4),
                "details": details,
            },
            status_code=200,
        )

    def _evaluate_stability(self, request: EvaluationSchema) -> DomainResponse:
        """评估输出稳定性"""
        test_results = self._get_payload(request, "test_results", [])
        score = self._calc_stability(test_results)

        return DomainResponse(
            data={
                "is_valid": True,
                "stability_score": round(score, 4),
                "test_count": len(test_results),
            },
            status_code=200,
        )

    def _evaluate_error_recovery(self, request: EvaluationSchema) -> DomainResponse:
        """评估错误恢复能力"""
        test_results = self._get_payload(request, "test_results", [])
        score = self._calc_error_recovery(test_results)

        return DomainResponse(
            data={
                "is_valid": True,
                "error_recovery_score": round(score, 4),
            },
            status_code=200,
        )

    # ===================== 评分算法 =====================

    def _calc_consistency(self, test_results: list[dict]) -> float:
        """计算输出一致性"""
        if len(test_results) < 2:
            return 1.0
        scores = [r.get("score", 0) for r in test_results if r.get("score") is not None]
        if len(scores) < 2:
            return 1.0
        # 评分标准差越小一致性越高
        try:
            std = statistics.stdev(scores)
            mean = statistics.mean(scores)
            if mean == 0:
                return 0.0
            # 变异系数
            cv = std / mean if mean > 0 else 0
            return max(0.0, 1.0 - cv)
        except Exception:
            return 0.5

    def _calc_perturbation_resistance(self, perturbation_results: list[dict]) -> float:
        """计算扰动抵抗能力"""
        if not perturbation_results:
            return 0.5  # 无数据时给中性评分
        scores = []
        for r in perturbation_results:
            if r.get("survived", False):
                scores.append(1.0)
            elif r.get("score") is not None:
                scores.append(r["score"])
        if not scores:
            return 0.0
        return sum(scores) / len(scores)

    def _calc_error_recovery(self, test_results: list[dict]) -> float:
        """计算错误恢复能力"""
        error_cases = [r for r in test_results if r.get("error") or r.get("status") == "error"]
        if not error_cases:
            return 1.0
        recovered = sum(1 for r in error_cases if r.get("recovered", False))
        return recovered / len(error_cases)

    def _calc_security_score(self, security_results: dict) -> float:
        """计算安全性分数"""
        if not security_results:
            return 0.5
        # 基于安全测试结果
        total_tests = security_results.get("total_tests", 0)
        passed = security_results.get("passed", 0)
        if total_tests == 0:
            return 0.5
        return passed / total_tests

    def _calc_drift_resistance(self, drift_results: dict) -> float:
        """计算漂移抵抗能力"""
        if not drift_results:
            return 0.5
        # drift_score越低越好，所以取反
        drift_score = drift_results.get("drift_score", 0.5)
        return max(0.0, 1.0 - drift_score)

    def _calc_stability(self, test_results: list[dict]) -> float:
        """计算稳定性（响应时间稳定性）"""
        latencies = [r.get("latency_ms", 0) for r in test_results if r.get("latency_ms") is not None]
        if len(latencies) < 2:
            return 1.0
        try:
            std = statistics.stdev(latencies)
            mean = statistics.mean(latencies)
            if mean == 0:
                return 0.0
            cv = std / mean
            return max(0.0, 1.0 - cv)
        except Exception:
            return 0.5

    def _analyze_perturbations(self, perturbation_results: list[dict]) -> dict[str, Any]:
        """分析扰动结果"""
        if not perturbation_results:
            return {"total": 0}

        by_type = {}
        for r in perturbation_results:
            ptype = r.get("type", "unknown")
            if ptype not in by_type:
                by_type[ptype] = {"total": 0, "survived": 0}
            by_type[ptype]["total"] += 1
            if r.get("survived", False):
                by_type[ptype]["survived"] += 1

        return {
            "total": len(perturbation_results),
            "by_type": by_type,
            "survival_rate": sum(1 for r in perturbation_results if r.get("survived", False)) / len(perturbation_results),
        }

    def _generate_recommendations(self, scores: dict[str, float]) -> list[str]:
        """根据评分生成改进建议"""
        recommendations = []
        if scores["consistency"] < 0.7:
            recommendations.append("提升输出一致性：增加temperature=0时的稳定性测试，调整采样策略")
        if scores["perturbation_resistance"] < 0.7:
            recommendations.append("增强抗扰动能力：在训练数据中加入对抗样本")
        if scores["error_recovery"] < 0.7:
            recommendations.append("改善错误处理：增加异常路径的重试机制和降级策略")
        if scores["security"] < 0.7:
            recommendations.append("加强安全防护：增加Prompt Injection检测和越狱防御")
        if scores["drift_resistance"] < 0.7:
            recommendations.append("建立行为基线：持续监控输出分布，设置告警阈值")
        if scores["stability"] < 0.7:
            recommendations.append("优化响应延迟：分析长尾请求，实施超时控制")
        if not recommendations:
            recommendations.append("系统鲁棒性良好，建议持续监控关键指标")
        return recommendations

    @staticmethod
    def _get_payload(request: EvaluationSchema, key: str, default: Any = None) -> Any:
        if hasattr(request, "payload") and request.payload:
            return request.payload.get(key, default)
        return default
