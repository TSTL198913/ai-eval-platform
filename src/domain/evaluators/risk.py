"""
📊 迭代优化风险评估器 - 智能化 Agent 持续演进演化风控引擎
支持多维度精准监控：功能蔓延、技术债务累积、模块耦合、测试覆盖及行为漂移风险。
升级 2026 高并发异步流支持，提供强类型防御边界，统一阈值管理，强化分值动态可观测性。
"""

import asyncio
import logging

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.schemas.evaluation import DomainResponse, EvaluationSchema

logger = logging.getLogger(__name__)


@EvaluatorFactory.register("risk")
class RiskEvaluator(BaseEvaluator):
    """迭代优化风险评估器（2026 异步高性能优化版）"""

    # 统一风险判定基准阈值（在 _get_risk_level 中执行标准归一化分级）
    RISK_THRESHOLDS = {
        "feature_creep": 0.7,
        "tech_debt": 0.6,
        "coupling": 0.5,
        "test_coverage_risk": 0.4,  # 转换统一模型：将覆盖率不足转化为“不足风险分”，标准阈值设为 0.4
        "drift": 0.2,
    }

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        """[同步轨] 执行风险防御流（向后兼容传统流）"""
        if error := self.validate_input(request):
            return error

        action = self.get_payload_data(request, "action", "detect_all")

        if action == "detect_all":
            return self._detect_all_risk(request)
        elif action in self.RISK_THRESHOLDS or action == "test_coverage":
            # 路由映射到对应的单项检测器
            method_name = f"_detect_{'test_coverage' if action == 'test_coverage' else action}"
            if hasattr(self, method_name):
                return getattr(self, method_name)(request)

        return DomainResponse(
            is_valid=False,
            error=f"🚨 未知的风险评估动作指令: {action}",
        )

    async def evaluate_async(self, request: EvaluationSchema) -> DomainResponse:
        """🚀 [异步轨] 非阻塞式高并发风险评估入口
        利用 asyncio.to_thread 隔绝大量浮点数运算和复杂的多级嵌套调用，保障主事件循环处于极致流畅状态。
        """
        return await asyncio.to_thread(self.evaluate, request)

    def _safe_float(self, request: EvaluationSchema, key: str, default: float) -> float:
        """🛡️ 强类型防御组件：确保从不确定类型的 payload 中安全剥离出 float，避免数学运算中暴死"""
        val = self.get_payload_data(request, key, default)
        if val is None:
            return default
        try:
            return float(val)
        except (ValueError, TypeError):
            logger.warning(
                f"⚠️ 风险评估器检测到无效的数值类型: key={key}, val={val}, 已降级使用默认值 {default}"
            )
            return default

    def _detect_all_risk(self, request: EvaluationSchema) -> DomainResponse:
        """聚合全维度风险审计（采用一票否决风控级别 + 高精可观测分值）"""
        feature_creep_res = self._detect_feature_creep(request)
        tech_debt_res = self._detect_tech_debt(request)
        coupling_res = self._detect_coupling(request)
        test_coverage_res = self._detect_test_coverage(request)
        drift_res = self._detect_drift(request)

        results = [
            ("feature_creep", feature_creep_res),
            ("tech_debt", tech_debt_res),
            ("coupling", coupling_res),
            ("test_coverage", test_coverage_res),
            ("drift", drift_res),
        ]

        high_risks = [name for name, res in results if res.data.get("risk_level") == "high"]
        medium_risks = [name for name, res in results if res.data.get("risk_level") == "medium"]

        # ⚖️ 风控红线对齐（木桶原理）：只要有一项高危，全局立刻熔断为 high
        overall_risk_level = "low"
        if high_risks:
            overall_risk_level = "high"
        elif medium_risks:
            overall_risk_level = "medium"

        # 🧠 2026 高精可观测性进化：计算真实综合分值（5项单项技术健康分数的算术平均值）
        # 避免原有阶梯截断导致的“债务缓慢蚕食却大盘全绿”现象
        exact_scores = [res.score for _, res in results if res.score is not None]
        avg_health_score = sum(exact_scores) / len(exact_scores) if exact_scores else 1.0

        return DomainResponse(
            is_valid=True,
            text=f"全面优化风险评估完成，当前判定为 [{overall_risk_level.upper()}] 风险等级。共拦截 {len(high_risks)} 项高危漏洞，{len(medium_risks)} 项潜在中度风险。",
            score=round(avg_health_score, 4),
            data={
                "overall_risk_level": overall_risk_level,
                "high_risks": high_risks,
                "medium_risks": medium_risks,
                "health_score": round(avg_health_score, 4),
                "details": {name: res.data for name, res in results},
            },
        )

    def _detect_feature_creep(self, request: EvaluationSchema) -> DomainResponse:
        """检测功能蔓延风险（边界模糊、核心偏离度）"""
        feature_complexity = self._safe_float(request, "feature_complexity", 0.0)
        core_alignment = self._safe_float(request, "core_alignment", 1.0)
        responsibility_blur = self._safe_float(request, "responsibility_blur", 0.0)

        risk_score = (
            (1.0 - core_alignment) * 0.5 + feature_complexity * 0.3 + responsibility_blur * 0.2
        )
        risk_level = self._get_risk_level(risk_score, self.RISK_THRESHOLDS["feature_creep"])

        return DomainResponse(
            is_valid=True,
            text=f"功能蔓延风险评估完成，判定级别: {risk_level}",
            score=max(0.0, 1.0 - risk_score),
            data={
                "risk_type": "feature_creep",
                "risk_level": risk_level,
                "risk_score": round(risk_score, 4),
                "metrics": {
                    "feature_complexity": feature_complexity,
                    "core_alignment": core_alignment,
                    "responsibility_blur": responsibility_blur,
                },
                "suggestion": "建议立即重新审计新增 Agent 功能域是否偏离最初产品规划的核心方向"
                if risk_level in ("medium", "high")
                else "功能边界控制极佳",
            },
        )

    def _detect_tech_debt(self, request: EvaluationSchema) -> DomainResponse:
        """检测技术债务累积风险（警告积压、重复率、重构挂起）"""
        unresolved_warnings = self._safe_float(request, "unresolved_warnings", 0.0)
        duplicate_code_ratio = self._safe_float(request, "duplicate_code_ratio", 0.0)
        pending_refactoring = self._safe_float(request, "pending_refactoring", 0.0)
        documentation_gap = self._safe_float(request, "documentation_gap", 0.0)

        risk_score = (
            min(unresolved_warnings / 100.0, 1.0) * 0.3
            + duplicate_code_ratio * 0.3
            + min(pending_refactoring / 10.0, 1.0) * 0.2
            + documentation_gap * 0.2
        )
        risk_level = self._get_risk_level(risk_score, self.RISK_THRESHOLDS["tech_debt"])

        return DomainResponse(
            is_valid=True,
            text=f"技术债务风险评估完成，判定级别: {risk_level}",
            score=max(0.0, 1.0 - risk_score),
            data={
                "risk_type": "tech_debt",
                "risk_level": risk_level,
                "risk_score": round(risk_score, 4),
                "metrics": {
                    "unresolved_warnings": unresolved_warnings,
                    "duplicate_code_ratio": duplicate_code_ratio,
                    "pending_refactoring": pending_refactoring,
                    "documentation_gap": documentation_gap,
                },
                "suggestion": "技术债务积累过高，强烈建议终止新功能冲刺，强行插入技术债务清理迭代"
                if risk_level in ("medium", "high")
                else "代码健康度良好",
            },
        )

    def _detect_coupling(self, request: EvaluationSchema) -> DomainResponse:
        """检测模块紧密耦合风险（循环依赖、跨层越权）"""
        external_dependencies = self._safe_float(request, "external_dependencies", 0.0)
        cyclic_dependencies = self._safe_float(request, "cyclic_dependencies", 0.0)
        cross_layer_calls = self._safe_float(request, "cross_layer_calls", 0.0)

        risk_score = (
            min(external_dependencies / 10.0, 1.0) * 0.5
            + cyclic_dependencies * 0.3
            + cross_layer_calls * 0.2
        )
        risk_level = self._get_risk_level(risk_score, self.RISK_THRESHOLDS["coupling"])

        return DomainResponse(
            is_valid=True,
            text=f"模块耦合风险评估完成，判定级别: {risk_level}",
            score=max(0.0, 1.0 - risk_score),
            data={
                "risk_type": "coupling",
                "risk_level": risk_level,
                "risk_score": round(risk_score, 4),
                "metrics": {
                    "external_dependencies": external_dependencies,
                    "cyclic_dependencies": cyclic_dependencies,
                    "cross_layer_calls": cross_layer_calls,
                },
                "suggestion": "检测到高风险架构耦合，建议提取抽象中间接口层或事件总线实施强行解耦"
                if risk_level in ("medium", "high")
                else "模块架构清晰，解耦良好",
            },
        )

    def _detect_test_coverage(self, request: EvaluationSchema) -> DomainResponse:
        """检测测试覆盖不足风险（对齐回归至统一的风险阈值评估模型）"""
        overall_coverage = self._safe_float(request, "overall_coverage", 0.0)
        new_code_coverage = self._safe_float(request, "new_code_coverage", 0.0)
        critical_path_coverage = self._safe_float(request, "critical_path_coverage", 0.0)
        test_pass_rate = self._safe_float(request, "test_pass_rate", 1.0)

        # 🧠 架构归一化：为了将“覆盖率不足”塞进标准的 “risk_score” 判定模型，
        # 基准合格线暂用 0.8（也可以提取到配置中），未达到合格线的部分累加为风险敞口
        TARGET_COV = 0.8
        risk_score = (
            max(0.0, TARGET_COV - overall_coverage) * 0.25
            + max(0.0, TARGET_COV - new_code_coverage) * 0.35
            + max(0.0, TARGET_COV - critical_path_coverage) * 0.25
            + (1.0 - test_pass_rate) * 0.15
        )

        # ✨ 修复硬编码漏洞：统一采用类配置的 RISK_THRESHOLDS 以及标准评估函数
        risk_level = self._get_risk_level(risk_score, self.RISK_THRESHOLDS["test_coverage_risk"])

        return DomainResponse(
            is_valid=True,
            text=f"测试覆盖风险评估完成，判定级别: {risk_level}",
            score=max(0.0, 1.0 - risk_score),
            data={
                "risk_type": "test_coverage",
                "risk_level": risk_level,
                "risk_score": round(risk_score, 4),
                "metrics": {
                    "overall_coverage": overall_coverage,
                    "new_code_coverage": new_code_coverage,
                    "critical_path_coverage": critical_path_coverage,
                    "test_pass_rate": test_pass_rate,
                },
                "suggestion": "核心变更路径缺乏自动化测试覆盖，存在严重的回归隐患，建议加急补齐单元测试"
                if risk_level in ("medium", "high")
                else "测试防护网构建完善",
            },
        )

    def _detect_drift(self, request: EvaluationSchema) -> DomainResponse:
        """检测系统行为漂移风险（基线偏差率、时延剧变、报错率突增）"""
        baseline_score = self._safe_float(request, "baseline_score", 0.0)
        current_score = self._safe_float(request, "current_score", 0.0)
        format_changes = self._safe_float(request, "format_changes", 0.0)
        latency_increase = self._safe_float(request, "latency_increase", 0.0)
        error_rate_change = self._safe_float(request, "error_rate_change", 0.0)

        score_drift = abs(baseline_score - current_score)
        risk_score = (
            score_drift * 0.4
            + min(format_changes / 10.0, 1.0) * 0.25
            + min(latency_increase / 100.0, 1.0) * 0.2
            + min(error_rate_change / 0.1, 1.0) * 0.15
        )
        risk_level = self._get_risk_level(risk_score, self.RISK_THRESHOLDS["drift"])

        return DomainResponse(
            is_valid=True,
            text=f"行为漂移风险评估完成，判定级别: {risk_level}",
            score=max(0.0, 1.0 - risk_score),
            data={
                "risk_type": "drift",
                "risk_level": risk_level,
                "risk_score": round(risk_score, 4),
                "metrics": {
                    "baseline_score": baseline_score,
                    "current_score": current_score,
                    "score_drift": score_drift,
                    "format_changes": format_changes,
                    "latency_increase": latency_increase,
                    "error_rate_change": error_rate_change,
                },
                "suggestion": "Agent 核心生成行为和响应耗时已大幅偏离系统历史锚定基线，建议回滚最近的 Prompt 或微调权重"
                if risk_level in ("medium", "high")
                else "系统运行基线极度稳健",
            },
        )

    def _get_risk_level(self, risk_score: float, threshold: float) -> str:
        """[基类覆盖/统一工具] 归一化判定标准风险区间"""
        if risk_score >= threshold:
            return "high"
        elif risk_score >= threshold * 0.5:
            return "medium"
        else:
            return "low"
